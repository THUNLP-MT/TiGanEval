'Deterministic, sandboxed reading of one start-up workspace.'

from __future__ import annotations

from collections import deque
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import (BOOT_SCENE, FAILING_SCENE, FAILING_SERVICE, TYPO_SCENE,
                       UNKNOWN_SCENE, build_program, connecting, serial_ticks)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("bootstrap/startup.py", "bootstrap/planner.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT, driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES, prefix="tiganeval-startup-")


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "morning-cold-start": "cold-start",
    "settlement-wave-failure": "wave-failure",
    "digest-cold-start": "start-less-chain",
    "manifest-typo-retry": "typo-retry",
}

BUCKETS: Mapping[str, str] = {
    "unwind_releases_started_services": "unwind_failures",
    "startup_order_follows_dependencies": "order_failures",
    "each_service_starts_once": "lifecycle_failures",
    "resolution_serves_started_instances": "resolution_failures",
    "start_up_within_the_deploy_window": "limit_failures",
}

_CACHE = AnalysisCache()
_CONTRACT: Any = None


def reference_contract() -> Any:
    "The frozen `bootstrap/contract.py`, loaded from the project's own tree, so     that the declared edges the review reads are the edges `Registry` itself     answers with rather than a second opinion about the manifest.."

    global _CONTRACT
    if _CONTRACT is None:
        path = TASK_ROOT / "workspace" / "bootstrap" / "contract.py"
        spec = importlib.util.spec_from_file_location("_bootstrap_contract_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _CONTRACT = module
    return _CONTRACT


def declared_edges(scene: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    'What each service declares it is built on, through the frozen registry.'

    contract = reference_contract()
    registry = contract.Registry()
    for entry in scene.get("manifest", ()):
        registry.register(str(entry["name"]), None, depends_on=entry.get("depends_on", ()))
    return {name: registry.declared_dependencies(name) for name in registry.names()}


def _reachable(edges: Mapping[str, Sequence[str]], name: str) -> set[str]:
    'Everything `name` is built on, directly or through anything else.'

    seen: set[str] = set()
    queue = deque(edges.get(name, ()))
    while queue:
        current = queue.popleft()
        if current in seen or current not in edges:
            continue
        seen.add(current)
        queue.extend(edges.get(current, ()))
    return seen


def _has_cycle(edges: Mapping[str, Sequence[str]]) -> bool:
    return any(name in _reachable(edges, name) for name in edges)


def _path(
    edges: Mapping[str, Sequence[str]], start: str, target: str, through: set[str] | None
) -> list[str] | None:
    'A shortest declared path from `start` down to `target`.'

    queue: deque[list[str]] = deque([[start]])
    seen = {start}
    while queue:
        route = queue.popleft()
        for nxt in edges.get(route[-1], ()):
            if nxt == target:
                return route + [nxt]
            if nxt in seen or nxt not in edges:
                continue
            if through is not None and nxt not in through:
                continue
            seen.add(nxt)
            queue.append(route + [nxt])
    return None


class Boot:
    'One scene, with the console ledger kept separate from host-observed work.'

    def __init__(self, result: Mapping[str, Any], scene: Mapping[str, Any]):
        self.name = str(result.get("name", ""))
        self.scene = scene
        self.config = dict(result.get("config", {}))
        self.entries = [dict(entry) for entry in result.get("ledger", ())]
        self.audit = [dict(entry) for entry in result.get("audit", ())]
        self.operations = [dict(op) for op in result.get("operations", ())]
        self.open_handles = [str(name) for name in result.get("actual_open_handles", ())]
        self.connecting = connecting(scene)
        self.base_edges = declared_edges(scene)
        self.runs = self._runs()

    def _runs(self) -> list[dict[str, Any]]:
        'Split host-observed work by the scripted bring-up that produced it.'

        edges = {name: tuple(value) for name, value in self.base_edges.items()}
        runs: list[dict[str, Any]] = []
        attempt = 0
        for position, raw in enumerate(self.scene.get("operations", ())):
            event = str(raw.get("op", ""))
            if event == "amend":
                edges = dict(edges)
                edges[str(raw["name"])] = tuple(str(x) for x in raw.get("depends_on", ()))
            elif event == "bring_up":
                operation = self.operations[position] if position < len(self.operations) else {}
                runs.append({
                    "index": attempt,
                    "entries": [row for row in self.audit
                                if int(row.get("attempt", -1)) == attempt],
                    "edges": dict(edges),
                    "error": operation.get("error"),
                    "elapsed": int(operation.get("elapsed_ticks", 0) or 0),
                })
                attempt += 1
        return runs

    def of(self, event: str, entries: Iterable[Mapping[str, Any]] | None = None) -> list[dict]:
        rows = self.audit if entries is None else entries
        return [dict(entry) for entry in rows if str(entry.get("event")) == event]

    def reported(self, event: str) -> list[dict[str, Any]]:
        'Candidate-written console ledger rows, used only where reporting matters.'

        return [dict(entry) for entry in self.entries
                if str(entry.get("event")) == event]

    def starts(self, name: str) -> int:
        return len([row for row in self.of("start_begin") if str(row.get("name")) == name])

    def bring_up_error(self, index: int) -> str:
        if index >= len(self.runs):
            return ""
        return str(self.runs[index].get("error") or "")

    def peak_in_flight(self) -> tuple[int, int, tuple[str, ...]]:
        'The most connect steps in flight at once, when, and which they were.'

        live: dict[str, int] = {}
        peak, moment, names = 0, 0, ()
        for entry in self.audit:
            event = str(entry.get("event"))
            if event == "start_begin":
                live[str(entry["name"])] = int(entry.get("at", 0))
            elif event in ("start_end", "start_error"):
                live.pop(str(entry.get("name")), None)
            else:
                continue
            if len(live) > peak:
                peak, moment, names = len(live), int(entry.get("at", 0)), tuple(sorted(live))
        return peak, moment, names


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _order_failures(boots: Sequence[Boot]) -> list[dict[str, Any]]:
    'Every service waits for everything it is built on, however it is reached.'

    failures: list[dict[str, Any]] = []
    for boot in boots:
        joined = set(boot.connecting)
        for run in boot.runs:
            edges = run["edges"]
            if _has_cycle(edges):
                continue
            begins: dict[str, dict[str, Any]] = {}
            ends: dict[str, dict[str, Any]] = {}
            for entry in run["entries"]:
                event, name = str(entry.get("event")), str(entry.get("name"))
                if event == "start_begin":
                    begins.setdefault(name, dict(entry))
                elif event == "start_end":
                    ends.setdefault(name, dict(entry))
            for service, begin in sorted(begins.items()):
                for dependency in sorted(_reachable(edges, service) & joined):
                    ready = ends.get(dependency)
                    if ready is None or int(ready["seq"]) < int(begin["seq"]):
                        continue
                    direct = _path(edges, service, dependency, joined - {service, dependency})
                    route = direct or _path(edges, service, dependency, None) or [service, dependency]
                    failures.append(_fail(
                        "dependent_started_before_its_dependency" if direct
                        else "order_ignored_a_service_without_a_connect_step",
                        service=service, dependency=dependency,
                        path=" <- ".join(route), configuration=boot.name,
                        started_at=int(begin.get("at", 0)),
                        dependency_ready_at=int(ready.get("at", 0))))
    return failures


def _stop_seqs(run: Mapping[str, Any]) -> list[int]:
    "The ledger positions of this attempt's stop steps, in order."

    return [int(entry["seq"]) for entry in run["entries"]
            if str(entry.get("event")) in ("release", "stop_error")]


def _open_handle_failures(boot: Boot) -> list[dict[str, Any]]:
    'Every handle the process still holds, and how it came to still hold it.'

    runs = {int(row["seq"]): run for run in boot.runs for row in run["entries"]}
    failures: list[dict[str, Any]] = []
    for name in boot.open_handles:
        taken = [row for row in boot.of("acquire") if str(row.get("name")) == name][-1:]
        seq = int(taken[0]["seq"]) if taken else -1
        stops = _stop_seqs(runs[seq]) if seq in runs else []
        late = bool(stops) and seq > max(stops)
        failures.append(_fail(
            "handle_taken_after_the_teardown" if late else "handle_never_given_back",
            service=name, open_handles=len(boot.open_handles),
            taken_at=int(taken[0]["at"]) if taken else 0))
    return failures


def _teardown_failures(boot: Boot, run: Mapping[str, Any]) -> list[dict[str, Any]]:
    "What one attempt's teardown stopped, in what order, and how often."

    connected = {str(row["name"]) for row in boot.of("start_end", run["entries"])}
    stop_errors = len(boot.of("stop_error", run["entries"]))
    counted: dict[str, int] = {}
    stops: list[dict[str, Any]] = []
    for entry in boot.of("release", run["entries"]):
        name = str(entry["name"])
        counted[name] = counted.get(name, 0) + 1
        if counted[name] == 1:
            stops.append(entry)
    failures: list[dict[str, Any]] = []


    up = [entry for entry in stops if str(entry["name"]) in connected]
    for position, entry in enumerate(up):
        service = str(entry["name"])
        for later in up[position + 1:]:
            if service in _reachable(run["edges"], str(later["name"])):
                failures.append(_fail(
                    "released_a_service_before_its_dependents", service=service,
                    dependent=str(later["name"]), released_at=int(entry["at"]),
                    stop_errors=stop_errors))
                break
    for entry in stops:
        service = str(entry["name"])
        if service not in connected:
            failures.append(_fail(
                "released_something_it_had_not_started", service=service,
                released_at=int(entry["at"]), connected=len(connected)))
        elif counted[service] > 1:
            failures.append(_fail(
                "stopped_the_same_service_twice", service=service,
                releases=counted[service], released_at=int(entry["at"]),
                stop_errors=stop_errors))
    return failures


def _unwind_failures(boots: Sequence[Boot]) -> list[dict[str, Any]]:
    'A deploy that fails leaves nothing connected and nothing held.'

    boot = next((item for item in boots if item.name == FAILING_SCENE), None)
    if boot is None or not boot.of("start_error"):
        return [_fail(
            "failing_service_was_not_attempted", service=FAILING_SERVICE,
            configuration=FAILING_SCENE)]
    failures = _open_handle_failures(boot)
    for run in boot.runs:
        failures.extend(_teardown_failures(boot, run))
    broke = [str(row["name"]) for row in boot.of("start_error")]
    reported = boot.bring_up_error(0) or "the deploy reported nothing wrong"
    if broke and FAILING_SERVICE in broke and FAILING_SERVICE not in reported:
        failures.append(_fail(
            "failure_named_the_wrong_service", service=FAILING_SERVICE,
            reported=reported, stop_errors=len(boot.of("stop_error"))))
    reported_stop_errors = {
        (str(row.get("name")), str(row.get("error")))
        for row in boot.reported("stop_error")
    }
    for row in boot.of("stop_error"):
        name, error = str(row.get("name")), str(row.get("error"))
        if (name, error) not in reported_stop_errors:
            failures.append(_fail(
                "stop_error_not_recorded", service=name, error=error,
                configuration=boot.name))
    return failures


def _lifecycle_failures(boots: Sequence[Boot]) -> list[dict[str, Any]]:
    'Every connect step runs once per process, and a rejected manifest is retryable.'

    failures: list[dict[str, Any]] = []
    for boot in boots:
        if boot.name in (TYPO_SCENE, UNKNOWN_SCENE) and boot.runs:
            rejected = boot.runs[0]
            if rejected.get("error"):
                failures.extend(
                    _fail("started_services_before_rejecting_the_manifest",
                          service=str(row["name"]), at=int(row.get("at", 0)),
                          configuration=boot.name)
                    for row in boot.of("start_begin", rejected["entries"]))
            elif boot.name == UNKNOWN_SCENE:
                failures.append(_fail(
                    "unknown_dependency_was_not_rejected",
                    service="receipt-writer", dependency="archive-pool",
                    configuration=boot.name))
        if boot.name in (TYPO_SCENE, UNKNOWN_SCENE) and len(boot.runs) > 1:
            after = [row for row in boot.of("start_begin", boot.runs[1]["entries"])]
            if not after:
                failures.append(_fail(
                    "retry_after_a_manifest_typo_refused" if boot.name == TYPO_SCENE
                    else "retry_after_an_unknown_dependency_refused",
                    services=", ".join(boot.connecting),
                    reported=boot.bring_up_error(1) or "nothing at all",
                    configuration=boot.name))
                continue
        for service in boot.connecting:
            starts = boot.starts(service)
            if starts > 1:
                failures.append(_fail(
                    "retry_after_a_failed_start_restarted_services"
                    if boot.name == FAILING_SCENE else "service_started_more_than_once",
                    service=service, starts=starts, configuration=boot.name))
            elif starts == 0 and boot.name != FAILING_SCENE:
                failures.append(_fail(
                    "service_never_started", service=service, configuration=boot.name))
    return failures


def _resolution_failures(boots: Sequence[Boot]) -> list[dict[str, Any]]:
    'What the process hands a caller is the object the connect step left.'

    failures: list[dict[str, Any]] = []
    for boot in boots:
        ready: dict[str, dict[str, Any]] = {}
        for entry in boot.audit:
            event, name = str(entry.get("event")), str(entry.get("name"))
            if event == "start_end":
                ready[name] = dict(entry)
                continue
            if event != "probe":
                continue
            connects = name in boot.connecting
            served, token = bool(entry.get("served")), str(entry.get("token", ""))
            if connects and served and name not in ready:
                failures.append(_fail(
                    "unstarted_service_handed_out", service=name,
                    at=int(entry.get("at", 0)), served_as=token, configuration=boot.name))
            elif (connects and not served and name not in ready
                  and str(entry.get("when")) == "after bring-up"):
                failures.append(_fail(
                    "service_missing_after_boot", service=name,
                    reported=str(entry.get("error", "")), configuration=boot.name))
            elif connects and name in ready and not served:
                failures.append(_fail(
                    "started_service_not_resolvable", service=name,
                    at=int(entry.get("at", 0)), reported=str(entry.get("error", "")),
                    configuration=boot.name))
            elif connects and name in ready and served:
                returned = str(ready[name].get("returned", ""))
                expected = name if returned in ("", "NoneType") else returned
                if token != expected:
                    failures.append(_fail(
                        "replacement_not_installed", service=name, served_as=token,
                        connected_as=expected, configuration=boot.name))
    return failures


def _limit_failures(boots: Sequence[Boot]) -> list[dict[str, Any]]:
    'The stack comes up inside the window and inside the slot limit.'

    failures: list[dict[str, Any]] = []
    for boot in boots:
        limit = int(boot.config.get("max_parallel_starts", 4))
        window = int(boot.config.get("deploy_window_ticks", 0))
        if boot.name == BOOT_SCENE and boot.runs:
            connected = {str(row.get("name"))
                         for row in boot.of("start_end", boot.runs[0]["entries"])}
            missing = [name for name in boot.connecting if name not in connected]
            elapsed = int(boot.runs[0].get("elapsed", 0))
            if missing:
                failures.append(_fail(
                    "boot_did_not_finish", service=missing[0],
                    connected=len(connected), expected=len(boot.connecting),
                    configuration=boot.name))
            elif elapsed > window:
                failures.append(_fail(
                    "deploy_window_overrun", elapsed_ticks=elapsed,
                    deploy_window_ticks=window, configuration=boot.name,
                    one_at_a_time_ticks=serial_ticks(boot.scene)))
        peak, moment, names = boot.peak_in_flight()
        if peak > limit:
            failures.append(_fail(
                "too_many_connects_at_once", peak_at_once=peak, max_parallel_starts=limit,
                at=moment, services=", ".join(names), configuration=boot.name))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    scenes = {str(scene["name"]): scene for scene in program.get("scenes", ())}
    boots = [Boot(result, scenes[str(result.get("name"))])
             for result in candidate.get("scenes", ()) if str(result.get("name")) in scenes]
    return {"unwind_failures": _unwind_failures(boots),
            "order_failures": _order_failures(boots),
            "lifecycle_failures": _lifecycle_failures(boots),
            "resolution_failures": _resolution_failures(boots),
            "limit_failures": _limit_failures(boots)}


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the deploy console shows when a start-up did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the process ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the process ended without saying why"
    return f"the start-up stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private review against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program), timeout=60.0)
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {
            "review": str(PRIVATE_CASE["profile"]),
            "scenes": len(program["scenes"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _manifest_rows(scene: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"service": str(entry["name"]), "declares": list(entry.get("depends_on", ())),
             "has_connect_step": "start" in entry}
            for entry in scene.get("manifest", ())]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        profile = PUBLIC_RECORDS.get(record_id)
        scene = build_program(profile)["scenes"][0] if profile else {}
        records.append({
            "record": f"project_records/{path.name}", "scene": raw.get("scene"),
            "services": [str(entry["name"]) for entry in scene.get("manifest", ())],
            "settings": dict(scene.get("config", {})),
            "connect_steps": len(connecting(scene)) if scene else 0})
    return {
        "summary": "The start-up workspace and the recorded start-ups the team replays.",
        "measurements": {
            "bootstrap_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "bootstrap").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


_LEDGER_FIELDS = {"start_begin": "connect_began_at", "start_end": "ready_at",
                  "start_error": "failed", "acquire": "took_at", "release": "gave_back_at"}


def _service_rows(boot: Boot) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for entry in boot.entries:
        event, name = str(entry.get("event")), str(entry.get("name"))
        if event not in _LEDGER_FIELDS:
            continue
        row = rows.setdefault(name, {"service": name, "connect_began_at": [], "ready_at": [],
                                     "returned": [], "failed": [], "took_at": [], "gave_back_at": []})
        row[_LEDGER_FIELDS[event]].append(
            entry.get("error") if event == "start_error" else int(entry.get("at", 0)))
        if event == "start_end":
            row["returned"].append(entry.get("returned"))
    return [rows[name] for name in sorted(rows)]


def _measured(boot: Boot) -> dict[str, Any]:
    peak, moment, names = boot.peak_in_flight()
    return {
        "elapsed_ticks_per_bring_up": [int(run.get("elapsed", 0)) for run in boot.runs],
        "deploy_window_ticks": int(boot.config.get("deploy_window_ticks", 0)),
        "one_connect_step_at_a_time_ticks": serial_ticks(boot.scene),
        "most_connect_steps_at_once": peak,
        "max_parallel_starts": int(boot.config.get("max_parallel_starts", 0)),
        "most_at_once_at_tick": moment,
        "most_at_once_were": list(names),
        "still_holding_at_the_end": list(boot.open_handles),
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded start-up and report the boot ledger.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    scene = program["scenes"][0]
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program), timeout=60.0)
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} start-up could not run against this build.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    results = [item for item in candidate.get("scenes", ()) if str(item.get("name")) == scene["name"]]
    boot = Boot(results[0], scene) if results else None
    if boot is None:
        raise ValueError(f"the console returned nothing for {record_id}")
    return {
        "summary": f"The {record_id} start-up ran against this build.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "settings": dict(boot.config),
        },
        "public": {
            "manifest": _manifest_rows(scene),
            "what_the_console_did": [
                {"operation": op.get("op"), "service": op.get("name"), "at_tick": op.get("at"),
                 "completed": op.get("ok"), "elapsed_ticks": op.get("elapsed_ticks"),
                 "error": op.get("error")}
                for op in boot.operations
            ],
            "boot_ledger": boot.entries,
            "per_service": _service_rows(boot),
            "measured": _measured(boot),
        },
    }
