'Deterministic, sandboxed review of one scripting-runtime workspace.'

from __future__ import annotations

from collections import Counter, defaultdict
import importlib.util
from itertools import zip_longest
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import (
    CYCLE_CHAIN,
    CYCLE_JOB,
    CYCLE_KEYS,
    EXPECTED_CATALOG,
    FAILING_KIT,
    FIRST_FAILING_JOB,
    FIRST_ORDER,
    LINKS,
    OTHER_WORKER,
    PINNED_RESOLUTION,
    RETRY_JOB,
    SECOND_ORDER,
    build_scenario,
    canonical,
    file_labels,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("runtime/loader.py", "runtime/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-runtime-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "nightly"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "nightly-2026-08-19": "incident",
    "worker-settings-swap": "settings-swap",
    "pilot-local-copy": "pilot-copy",
    "queue-order-swap": "order-swap",
}

BUCKETS: Mapping[str, str] = {
    "single_activation_per_file": "activation_failures",
    "resolution_agreement": "resolution_failures",
    "load_state_conservation": "load_state_failures",
    "run_outcome_independence": "outcome_failures",
    "loader_diagnostics_routing": "diagnostics_failures",
}

TRACE_OFF = ("", "0", "off", "false", "no")
TRACE_FLAG = "--trace"
NOTHING = "nothing"

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `runtime/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "runtime" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_runtime_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() not in TRACE_OFF


def _enabled(job: Mapping[str, Any]) -> bool:
    settings = dict(job.get("settings", {}))
    return _truthy(settings.get("trace")) or TRACE_FLAG in list(job.get("invocation", ()))


def _rows(catalog: Iterable[Mapping[str, Any]]) -> list[tuple[str, Any]]:
    "One run's catalog as entries in an order the publish order cannot move."

    return sorted(((str(entry.get("key")), entry.get("value")) for entry in catalog),
                  key=lambda row: (row[0], str(row[1])))


def _by_key(rows: Sequence[tuple[str, Any]]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for key, value in rows:
        grouped[key].append(value)
    return grouped


def _first_difference(
    left: Sequence[tuple[str, Any]], right: Sequence[tuple[str, Any]]
) -> tuple[str, Any, Any]:
    'The first key two catalogs disagree on, as (key, left value, right value).'

    one, two = _by_key(left), _by_key(right)
    for key in sorted(set(one) | set(two)):
        mine, theirs = one.get(key, []), two.get(key, [])
        if mine == theirs:
            continue
        for index in range(max(len(mine), len(theirs))):
            here = mine[index] if index < len(mine) else NOTHING
            there = theirs[index] if index < len(theirs) else NOTHING
            if here != there:
                return (key, here, there)
    return (NOTHING, NOTHING, NOTHING)


class Review:
    'Everything the five checks read from one drive of the private queue.'

    def __init__(self, outcome: Mapping[str, Any], scenario: Mapping[str, Any]):
        self.runs = [dict(run) for run in outcome.get("runs", ())]
        self.console = str(outcome.get("process_console", ""))
        self.labels = file_labels(scenario)
        self.paths = {label: path for path, label in self.labels.items()}

    def run(self, run_id: str) -> dict[str, Any]:
        return next((run for run in self.runs if str(run.get("run")) == run_id), {})

    def path_of(self, label: Any) -> str:
        return self.paths.get(str(label), NOTHING if label in (None, "None") else str(label))

    def kit_of(self, label: Any) -> str:
        tail = self.path_of(label).rsplit("/", 1)[-1]
        return tail[:-4] if tail.endswith(".kit") else tail

    def jobs(self, run: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(job.get("job")): dict(job) for job in run.get("jobs", ())}

    def asks(self, run: Mapping[str, Any]) -> dict[tuple[str, str, str], tuple[str, ...]]:
        'What each ask of one run reached, keyed by (job, asking file, name).'

        reached: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for use in run.get("uses", ()):
            key = (str(use.get("job")), canonical(use.get("origin")), str(use.get("name")))
            reached[key].add(self.path_of(use.get("file")) if use.get("ok") else NOTHING)
        return {key: tuple(sorted(files)) for key, files in reached.items()}


def _activation_failures(review: Review) -> list[dict[str, Any]]:
    'One kit file, one activation, one licence check per run.'

    failures: list[dict[str, Any]] = []
    for run in review.runs:
        billed: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in run.get("licence_checks", ()):
            billed[str(record.get("file"))].append(record)
        checks, brought_up = sum(len(rows) for rows in billed.values()), len(billed)
        for label, records in sorted(billed.items()):
            if len(records) < 2:
                continue
            jobs = Counter(str(record.get("job")) for record in records)
            spelled = len({str(record.get("asked")) for record in records})
            busiest, in_one_job = sorted(jobs.items(), key=lambda item: (-item[1], item[0]))[0]
            if in_one_job > 1:
                kind = "cached_kit_activated_again"
            elif spelled > 1:
                kind = "file_activated_under_a_second_name"
            else:
                kind = "file_activated_again_for_another_job"
            failures.append(_fail(
                kind, run=str(run.get("run")), kit=review.kit_of(label),
                file=review.path_of(label), activations=len(records), spellings=spelled,
                jobs=len(jobs), job=busiest, in_one_job=in_one_job,
                licence_checks=checks, kits_brought_up=brought_up))
    return failures


def _resolution_failures(review: Review) -> list[dict[str, Any]]:
    'Which file a name reaches, and its independence from how a worker is set up.'

    failures: list[dict[str, Any]] = []
    for run in review.runs:
        for origin, name, expected, kind in PINNED_RESOLUTION:
            wanted = review.labels.get(expected)
            for use in run.get("uses", ()):
                if not use.get("ok") or str(use.get("name")) != name:
                    continue
                if canonical(use.get("origin")) != origin or str(use.get("file")) == wanted:
                    continue
                failures.append(_fail(
                    kind, run=str(run.get("run")), job=str(use.get("job")), name=name,
                    kit=review.kit_of(use.get("file")), opened=review.path_of(use.get("file")),
                    expected=expected, asked_by=origin))

    here, there = review.asks(review.run(FIRST_ORDER)), review.asks(review.run(OTHER_WORKER))
    for key in sorted(set(here) & set(there)):
        if here[key] == there[key]:
            continue
        job, asked_by, name = key
        failures.append(_fail(
            "worker_settings_changed_the_result", run=OTHER_WORKER, job=job, name=name,
            asked_by=asked_by, opened=there[key][0], other=here[key][0]))
        break

    for run in review.runs:
        for use in run.get("uses", ()):
            if str(use.get("error")) == "MissingKit":
                failures.append(_fail(
                    "kit_name_not_found", run=str(run.get("run")), job=str(use.get("job")),
                    name=str(use.get("name")), asked_by=canonical(use.get("origin"))))
    return failures


def _load_state_failures(review: Review) -> list[dict[str, Any]]:
    'What a refused load and a loop leave behind.'

    read_cycle_chain = reference_protocol().read_cycle_chain
    failures: list[dict[str, Any]] = []
    failing = review.labels.get(FAILING_KIT)
    for run in review.runs:
        jobs = review.jobs(run)
        ended = dict(jobs.get(CYCLE_JOB, {}).get("ended") or {})
        if CYCLE_JOB in jobs:
            if not ended.get("loop"):
                failures.append(_fail(
                    "cycle_not_refused", run=str(run.get("run")), job=CYCLE_JOB,
                    stopped_with=str(ended.get("stopped_with") or "nothing at all"),
                    kits=len(CYCLE_CHAIN)))
            else:
                chain = tuple(str(item) for item in ended.get("chain", ()))
                named = read_cycle_chain([review.path_of(item) for item in chain])
                if named != CYCLE_CHAIN:
                    failures.append(_fail(
                        "cycle_chain_incomplete", run=str(run.get("run")), job=CYCLE_JOB,
                        chain=" then ".join(chain) or NOTHING,
                        kits_named=" then ".join(named) or NOTHING,
                        started_at=named[0] if named else NOTHING,
                        named=len(named), kits=len(CYCLE_CHAIN)))
        retry = dict(jobs.get(RETRY_JOB, {}).get("ended") or {})
        first = dict(jobs.get(FIRST_FAILING_JOB, {}).get("ended") or {})
        opened = sum(1 for entry in run.get("files_opened", ())
                     if str(entry.get("file")) == failing)
        if RETRY_JOB in jobs and not retry.get("refused"):
            failures.append(_fail(
                "failed_kit_left_behind", run=str(run.get("run")), job=RETRY_JOB,
                kit=review.kit_of(failing), opened=opened,
                stopped_with=str(retry.get("stopped_with") or "nothing at all"),
                first_stopped_with=str(first.get("stopped_with") or "nothing at all")))
    return failures


def _held(run: Mapping[str, Any]) -> tuple[str, ...]:
    "The kits one run's loader said it was holding when the run ended."

    return tuple(str(item) for item in (run.get("loader_holds") or ()))


def _outcome_failures(review: Review) -> list[dict[str, Any]]:
    'What the run ends with and what it reports holding, and their independence     from the dispatch order.'

    failures: list[dict[str, Any]] = []
    catalogs = {str(run.get("run")): _rows(run.get("catalog", ())) for run in review.runs}
    first, second = catalogs.get(FIRST_ORDER, []), catalogs.get(SECOND_ORDER, [])
    if first != second:
        key, one, two = _first_difference(first, second)
        failures.append(_fail(
            "run_depended_on_the_queue_order", run=SECOND_ORDER, key=key, first=one,
            second=two, entries=len(first), other_entries=len(second)))
    for run in review.runs:
        half = [entry for entry in run.get("catalog", ())
                if str(entry.get("key")).startswith(CYCLE_KEYS)]
        if half:
            failures.append(_fail(
                "half_built_kit_was_handed_out", run=str(run.get("run")),
                key=str(half[0].get("key")), value=half[0].get("value"), entries=len(half),
                job=CYCLE_JOB))
    expected = list(EXPECTED_CATALOG)
    for run in review.runs:
        rows = catalogs[str(run.get("run"))]
        if rows != expected:
            key, one, two = _first_difference(rows, expected)
            failures.append(_fail(
                "catalog_did_not_match_the_kit_files", run=str(run.get("run")), key=key,
                observed=one, expected=two, entries=len(rows),
                expected_entries=len(expected)))
    here, there = _held(review.run(FIRST_ORDER)), _held(review.run(SECOND_ORDER))
    if here != there:
        lines = list(zip_longest(here, there, fillvalue=NOTHING))
        moved = sum(1 for one, two in lines if one != two)
        at = next((number for number, (one, two) in enumerate(lines, start=1) if one != two), 0)
        failures.append(_fail(
            "held_kits_listed_in_dispatch_order", run=SECOND_ORDER, moved=moved, at=at,
            entries=len(here), other_entries=len(there)))
    return failures


def _log_problems(review: Review, run: Mapping[str, Any],
                  job: Mapping[str, Any]) -> list[dict[str, Any]]:
    read_trace_line = reference_protocol().read_trace_line
    name, log = str(job.get("job")), list(job.get("runtime_log", ()))
    if not _enabled(job):
        if log:
            return [_fail("job_log_did_not_match_the_job", run=str(run.get("run")), job=name,
                          event="line", counted=len(log), expected=0)]
        return []
    uses = [use for use in run.get("uses", ()) if str(use.get("job")) == name]
    if any(not use.get("ok") for use in uses):
        return []
    activations = sum(1 for record in run.get("licence_checks", ())
                      if str(record.get("job")) == name)
    expected = {"resolve": len(uses), "activate": activations,
                "hit": max(len(uses) - activations, 0)}
    counted = Counter()
    unreadable = 0
    for line in log:
        parsed = read_trace_line(line)
        if parsed is None:
            unreadable += 1
        else:
            counted[parsed[0]] += 1
    if unreadable:
        return [_fail("job_log_did_not_match_the_job", run=str(run.get("run")), job=name,
                      event="loader line", counted=len(log), expected=len(log) - unreadable)]
    for event in ("hit", "activate", "resolve"):
        if counted[event] != expected[event]:
            return [_fail("job_log_did_not_match_the_job", run=str(run.get("run")), job=name,
                          event=event, counted=counted[event], expected=expected[event])]
    return []


def _diagnostics_failures(review: Review) -> list[dict[str, Any]]:
    'Where the loader talks, and whether every event is there once.'

    failures: list[dict[str, Any]] = []
    console = [line for line in review.console.splitlines() if line.strip()]
    if console:
        failures.append(_fail(
            "diagnostics_went_to_the_process_stream", run=str(
                review.runs[0].get("run") if review.runs else NOTHING),
            lines=len(console), first_line=console[0].strip()[:80]))
    for run in review.runs:
        asking = [job for job in run.get("jobs", ()) if _enabled(job)]
        speaking = [job for job in asking if job.get("runtime_log")]
        if asking and not speaking:
            failures.append(_fail(
                "nothing_reached_the_job_logs", run=str(run.get("run")),
                job=str(asking[0].get("job")), jobs_asking=len(asking)))
            continue
        by_switch = [job for job in asking
                     if TRACE_FLAG in list(job.get("invocation", ()))
                     and not _truthy(dict(job.get("settings", {})).get("trace"))
                     and not job.get("runtime_log")]
        if by_switch and speaking:
            failures.append(_fail(
                "command_line_switch_ignored", run=str(run.get("run")),
                job=str(by_switch[0].get("job")), other_job=str(speaking[0].get("job")),
                other_lines=len(speaking[0].get("runtime_log", ()))))
            continue
        for job in run.get("jobs", ()):
            failures.extend(_log_problems(review, run, job))
    return failures


def _analyse(outcome: Mapping[str, Any], scenario: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(outcome, scenario)
    return {
        "activation_failures": _activation_failures(review),
        "resolution_failures": _resolution_failures(review),
        "load_state_failures": _load_state_failures(review),
        "outcome_failures": _outcome_failures(review),
        "diagnostics_failures": _diagnostics_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(outcome: Mapping[str, Any]) -> str:
    'The one line the console shows when a drive of the queue did not finish.'

    reported = str(outcome.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still going after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(outcome.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the worker ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the worker ended without saying why"
    return f"the worker stopped part way through the queue: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Drive the private nightly queue against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        scenario = build_scenario(str(PRIVATE_CASE["profile"]))
        outcome = PROJECT.invoke(artifact_dir, {"scenario": scenario})
        if not outcome.get("ok"):
            analysis = dict(failed_analysis(_console_error(outcome), tuple(BUCKETS.values())))
            diagnostic = outcome.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(outcome, scenario)
        analysis["case"] = {
            "queue": str(PRIVATE_CASE["profile"]),
            "runs": len(scenario["runs"]),
            "jobs": sum(len(run["jobs"]) for run in scenario["runs"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        scenario = (
            build_scenario(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else {}
        )
        records.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "runs": [
                {"run": run["id"],
                 "jobs": [job["id"] for job in run["jobs"]],
                 "kit_path": [job["settings"].get("kit_path") for job in run["jobs"]][:1]}
                for run in scenario.get("runs", ())
            ],
        })
    return {
        "summary": "The runtime workspace, the deployment's store, and the stretches the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "runtime_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "runtime").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "store_link_table": dict(LINKS),
            "store_tree": sorted(
                "/" + path.relative_to(root / "store").as_posix()
                for path in (root / "store").rglob("*.kit")
            ),
        },
        "records": records,
    }


PROBE_LINES = 120


def _run_view(run: Mapping[str, Any]) -> dict[str, Any]:
    'One run of a stretch, with the long lists printed a line each.'

    billed = Counter(str(record.get("file")) for record in run.get("licence_checks", ()))
    probes = list(run.get("store_was_asked_for", ()))
    return {
        "run": run.get("run"),
        "jobs": [
            {
                "job": job.get("job"),
                "path": job.get("path"),
                "settings": job.get("settings"),
                "invocation": job.get("invocation"),
                "declarations": job.get("declarations"),
                "job_log": job.get("runtime_log"),
                "ended": job.get("ended"),
            }
            for job in run.get("jobs", ())
        ],
        "what_each_use_reached": [
            f"{use.get('job')}: {use.get('origin')} use {use.get('name')} -> "
            + (str(use.get("file")) if use.get("ok") else f"stopped, {use.get('error')}")
            for use in run.get("uses", ())
        ],
        "what_the_store_was_asked_for": [
            f"{probe.get('asked')} -> {'found' if probe.get('found') else 'nothing there'}"
            for probe in probes[:PROBE_LINES]
        ] + ([f"... and {len(probes) - PROBE_LINES} more"] if len(probes) > PROBE_LINES else []),
        "files_opened": [
            f"{entry.get('asked')} -> {entry.get('file')}"
            for entry in run.get("files_opened", ())
        ],
        "licence_checks": [
            f"{record.get('job')} brought up {record.get('file')} read as {record.get('asked')}"
            for record in run.get("licence_checks", ())
        ],
        "totals": {
            "licence_checks_billed": sum(billed.values()),
            "distinct_kit_files_brought_up": len(billed),
        },
        "catalog_at_the_end": [
            f"{entry.get('key')} = {entry.get('value')}" for entry in run.get("catalog", ())
        ],
        "loader_report": run.get("loader_report"),
        "loader_holds": run.get("loader_holds"),
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded stretch and report what the console and the store saw.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    scenario = build_scenario(PUBLIC_RECORDS[record_id])
    outcome = PROJECT.invoke(Path(artifact_dir), {"scenario": scenario})
    if not outcome.get("ok"):
        return {
            "summary": f"The {record_id} stretch could not run against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": outcome.get("error", "unknown failure"),
                "diagnostic": outcome.get("diagnostic"),
            },
        }
    return {
        "summary": f"The {record_id} stretch ran against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "store_link_table": dict(LINKS),
            "runs": len(scenario["runs"]),
        },
        "public": {
            "runs": [_run_view(run) for run in outcome.get("runs", ())],
            "process_console": outcome.get("process_console"),
        },
    }
