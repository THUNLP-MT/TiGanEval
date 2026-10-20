'Deterministic, sandboxed review of one night runner.'

from __future__ import annotations

from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from . import workload


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("harness/sequencing.py", "harness/rendezvous.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-devicelab-",
)


PRIVATE_CASE: Mapping[str, Any] = {"session": workload.PRIVATE_SESSION}


PUBLIC_RECORDS: tuple[str, ...] = tuple(sorted(workload.PUBLIC_SESSIONS))

BUCKETS: Mapping[str, str] = {
    "record_attribution": "attribution_failures",
    "gate_scope_and_lifetime": "gate_scope_failures",
    "gate_party_from_bench": "gate_party_failures",
    "context_binding_contract": "context_failures",
    "night_envelope": "envelope_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None
_INVENTORY: Any = None


def reference_protocol() -> Any:
    "The frozen `harness/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "harness" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_devicelab_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def inventory() -> Mapping[str, Any]:
    'The lab inventory, read once from the frozen `lab_devices.json`.'

    global _INVENTORY
    if _INVENTORY is None:
        _INVENTORY = reference_protocol().load_inventory(
            TASK_ROOT / "workspace" / "lab_devices.json"
        )
    return _INVENTORY


def _text(value: Any) -> str:
    return "nothing at all" if value is None else str(value)


def _quoted(value: Any, missing: str = "nothing at all") -> str:
    'A value the delivered runner produced, as the lead may quote it: a line     the runner wrote cannot put a word into her mouth that she would not use.'

    line = (missing if value is None else str(value)).strip()[:80] or missing
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "something the log does not name"
    return line


def _execution_scope(phase: Any, bench: Any, case: Any, handset: Any) -> str:
    'A human-readable phase location without serialized ``None`` values.'

    phase_name = str(phase)
    case_name, bench_name, handset_name = str(case), str(bench), str(handset)
    if case_name not in ("", "None"):
        return f"case {case_name} on {bench_name} for {handset_name}"
    if bench_name not in ("", "None"):
        return f"{phase_name} on {bench_name} for {handset_name}"
    return phase_name


def _meeting_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, int]:
    return (str(row.get("bench")), str(row.get("phase")), str(row.get("case")),
            str(row.get("gate")), int(row.get("index", -1)))


class Night:
    'Everything the five checks read from one run of one session.'

    def __init__(self, report: Mapping[str, Any], spec: Mapping[str, Any]):
        self.report, self.spec = report, spec
        self.steps: list[dict[str, Any]] = [dict(row) for row in report.get("steps", ())]
        self.records: list[dict[str, Any]] = [dict(row) for row in report.get("records", ())]
        self.benches = workload.benches(spec, inventory())
        self.expected_meetings = workload.expected_meetings(spec, inventory())
        self.arrivals: dict[tuple[Any, ...], list[tuple[int, str]]] = defaultdict(list)
        self.resumes: dict[tuple[Any, ...], list[tuple[int, str]]] = defaultdict(list)
        self.phases_seen: set[tuple[str, str, str]] = set()
        self.checks: list[dict[str, Any]] = []
        for position, row in enumerate(self.steps):
            op = str(row.get("op"))
            self.phases_seen.add(
                (str(row.get("bench")), str(row.get("phase")), str(row.get("case"))))
            if op == "wait":
                self.arrivals[_meeting_key(row)].append((position, str(row.get("handset"))))
            elif op == "resume":
                self.resumes[_meeting_key(row)].append((position, str(row.get("handset"))))
            elif op == "check":
                self.checks.append({**row, "position": position})

    def phase_runs(self, phase: str) -> int:
        'How many times a session-wide phase started.'

        return sum(1 for row in self.steps
                   if str(row.get("phase")) == phase and int(row.get("index", -1)) == 0)

    def started_at(self, *, phase: str = "", bench: str = "") -> int | None:
        'Where in the night a phase, or a bench, first wrote a line.'

        return next((position for position, row in enumerate(self.steps)
                     if (not phase or str(row.get("phase")) == phase)
                     and (not bench or str(row.get("bench")) == bench)), None)

    def benches_reached(self) -> list[str]:
        seen = {str(row.get("bench")) for row in self.steps}
        return [bench for bench in self.benches if bench in seen]

    def bench_ran_phase(self, bench: str, phase: str) -> bool:
        return any(str(row.get("bench")) == bench and str(row.get("phase")) == phase
                   for row in self.steps)

    def phase_drivers(self, bench: str, phase: str) -> list[str]:
        'The handsets a bench-wide phase was run on, in inventory order.'

        driven = {str(row.get("handset")) for row in self.steps
                  if str(row.get("bench")) == bench and str(row.get("phase")) == phase}
        return [handset for handset in self.benches.get(bench, ()) if handset in driven]

    def bench_phase_runs(self, bench: str, phase: str) -> int:
        'How many executions of one bench-wide phase started.'

        return sum(1 for row in self.steps
                   if str(row.get("bench")) == bench
                   and str(row.get("phase")) == phase
                   and int(row.get("index", -1)) == 0)

    def name_arrivals(self, gate: str) -> list[tuple[int, tuple[Any, ...]]]:
        'Every arrival at a point of this name anywhere in the night.'

        return sorted((position, key)
                      for key, rows in self.arrivals.items() if key[3] == gate
                      for position, _ in rows)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _attribution_failures(night: Night) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    counted = Counter((str(row.get("case")), str(row.get("handset")),
                       str(row.get("bench")))
                      for row in night.records)
    expected = workload.expected_records(night.spec, inventory())
    expected_by_run = {(case, handset): bench for case, handset, bench in expected}
    for row in night.records:
        case, handset = str(row.get("case")), str(row.get("handset"))
        expected_bench = expected_by_run.get((case, handset))
        actual_bench = str(row.get("bench"))
        if expected_bench is not None and actual_bench != expected_bench:
            failures.append(_fail(
                "row_on_wrong_bench", case=case, handset=handset,
                expected=expected_bench, written=actual_bench))


    for case, handset, bench in expected:
        found = counted.pop((case, handset, bench), 0)
        if found == 0:
            failures.append(_fail(
                "no_row_for_a_handset", case=case, handset=handset, bench=bench,
                expected_rows=len(night.benches[bench])))
        elif found > 1:
            failures.append(_fail(
                "two_rows_for_one_handset", case=case, handset=handset, bench=bench,
                found=found))
    for (case, handset, bench), found in sorted(counted.items()):
        failures.append(_fail(
            "row_for_a_case_the_bench_did_not_run", case=case, handset=handset,
            bench=bench, found=found))

    expected_states = workload.expected_record_states(night.spec, inventory())
    actual_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in night.records:
        key = (str(row.get("case")), str(row.get("handset")), str(row.get("bench")))
        actual_rows[key].append(row)
    for key, (expected_flags, expected_outcome) in expected_states.items():
        rows = actual_rows.get(key, [])
        if len(rows) != 1:
            continue
        row = rows[0]
        extras = [str(flag) for flag in row.get("flags", ())
                  if str(flag) not in expected_flags]
        if extras:
            failures.append(_fail(
                "unexpected_flag_on_report", case=key[0], handset=key[1],
                bench=key[2], flag=extras[0]))
        actual_outcome = str(row.get("outcome"))
        if actual_outcome != expected_outcome:
            failures.append(_fail(
                "wrong_case_outcome", case=key[0], handset=key[1], bench=key[2],
                expected=expected_outcome, written=actual_outcome))

        ran = any(str(step.get("phase")) == "case"
                  and str(step.get("bench")) == key[2]
                  and str(step.get("case")) == key[0]
                  and str(step.get("handset")) == key[1]
                  for step in night.steps)
        if not ran:
            failures.append(_fail(
                "case_not_run_for_handset", case=key[0], handset=key[1], bench=key[2]))

    written: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in night.records:
        for text in row.get("flags", ()):
            written[(str(row.get("case")), str(text))].append(str(row.get("handset")))
    for case, handset, text in workload.expected_flags(night.spec, inventory()):
        rows = written.get((case, text), [])
        if not rows:
            failures.append(_fail(
                "flag_lost_between_records", case=case, handset=handset, flag=text))
        elif len(rows) > 1:
            failures.append(_fail(
                "flag_landed_on_several_records", case=case, handset=handset, flag=text,
                rows=len(rows)))
        elif rows[0] != handset:
            failures.append(_fail(
                "flag_landed_on_another_handset", case=case, handset=handset, flag=text,
                written_to=rows[0], bench=str(inventory()[handset].bench)))
    return failures


def _gate_scope_failures(night: Night) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for key, party_handsets in sorted(night.expected_meetings.items()):
        bench, phase, case, gate, index = key
        resumes = night.resumes.get(key, [])
        arrivals = night.arrivals.get(key, [])
        if not resumes or not arrivals:
            continue
        first_resume = min(position for position, _ in resumes)
        party = len(party_handsets)
        before = [handset for position, handset in arrivals if position < first_resume]
        own_before = len(before)
        if Counter(before) == Counter(str(item) for item in party_handsets):
            continue
        earlier = [other for position, other in night.name_arrivals(gate)
                   if other != key and position < first_resume]
        inside = [other for other in earlier if other[0] == bench and other[2] == case]
        expected_handsets = [str(item) for item in party_handsets]
        scope = f"case {case}" if phase == "case" else f"{phase} phase"
        shared = dict(
            gate=gate,
            bench=bench,
            case=case,
            phase=phase,
            scope=scope,
            party=party,
            arrived=own_before,
            arrived_handsets=", ".join(_quoted(item) for item in before) or "none",
            expected_handsets=", ".join(expected_handsets) or "none",
        )
        if not earlier:
            failures.append(_fail("gate_did_not_hold", **shared))
        elif inside:
            failures.append(_fail(
                "gate_reused_inside_the_case", use=len(set(inside)) + 1, **shared))
        else:
            failures.append(_fail(
                "gate_reused_across_the_night", earlier_bench=earlier[-1][0],
                earlier_case=earlier[-1][2], **shared))
    return failures


def _gate_party_failures(night: Night) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for key, party_handsets in sorted(night.expected_meetings.items()):
        bench, phase, case, gate, index = key
        arrivals = night.arrivals.get(key, [])
        resumes = night.resumes.get(key, [])
        party = len(party_handsets)
        arrived_handsets = [handset for _, handset in arrivals]
        expected_handsets = [str(handset) for handset in party_handsets]
        if arrivals and len(resumes) < len(arrivals):
            if phase == "case":
                failures.append(_fail(
                    "handsets_left_waiting", gate=gate, bench=bench, case=case,
                    party=party, arrived=len(arrivals),
                    waiting=len(arrivals) - len(resumes)))
            else:
                failures.append(_fail(
                    "bench_gate_blocked", gate=gate, bench=bench, phase=phase,
                    arrived=len(arrivals)))
        elif phase == "case" and Counter(arrived_handsets) != Counter(expected_handsets):
            failures.append(_fail(
                "bench_did_not_all_meet", gate=gate, bench=bench, case=case,
                party=party, arrived=len(set(arrived_handsets))))
        elif phase != "case" and not arrivals:
            failures.append(_fail(
                "bench_gate_blocked", gate=gate, bench=bench, phase=phase, arrived=0))


    for bench in night.benches_reached():
        for phase in workload.BENCH_PHASES:
            drivers = night.phase_drivers(bench, phase)
            if len(drivers) > 1:
                failures.append(_fail(
                    "bench_phase_ran_on_every_handset", bench=bench, phase=phase,
                    runs=len(drivers), handsets=", ".join(drivers)))
            runs = night.bench_phase_runs(bench, phase)
            if runs != 1 and len(drivers) <= 1:
                failures.append(_fail(
                    "bench_phase_run_count_wrong", bench=bench, phase=phase,
                    runs=runs, handsets=", ".join(drivers) or "none"))
    return failures


def _expected_check(protocol: Any, row: Mapping[str, Any]) -> dict[str, Any]:
    'What the frozen contract says this probe should have got back.'

    phase, ask = str(row.get("phase")), str(row.get("ask"))
    if ask == "gate":
        try:
            protocol.check_gate_request(phase, row.get("timeout"))
        except BaseException as exc:
            return {"error": type(exc).__name__,
                    "details": dict(getattr(exc, "details", {}) or {})}
        return {"value": "returned"}
    if phase in protocol.HANDSET_PHASES:
        return {"value": str(row.get("handset"))}
    exc = protocol.unbound_context(ask, phase)
    return {"error": type(exc).__name__, "details": dict(exc.details)}


def _verdict(row: Mapping[str, Any], expected: Mapping[str, Any]) -> str:
    "How this probe's answer differs from the frozen contract's, if it does."

    if "value" in expected:
        if row.get("error") is not None:
            return "raised_instead"
        return "ok" if str(row.get("value")) == expected["value"] else "wrong_value"
    if row.get("error") is None:
        return "answered_instead"
    if str(row.get("error")) != expected["error"]:
        return "wrong_kind"
    seen = dict(row.get("details") or {})
    if all(str(seen.get(key)) == str(value) for key, value in expected["details"].items()):
        return "ok"
    return "thin_details"


def _alert_said(row: Mapping[str, Any], expected: Mapping[str, Any]) -> str:
    'What the alert carried, over the fields the person paged needs.'

    seen = dict(row.get("details") or {})
    parts = [f"{key}={_quoted(seen.get(key), 'nothing')}"
             for key in sorted(expected.get("details", {}))]
    return ", ".join(parts) if parts else "nothing at all"


def _context_failures(night: Night) -> list[dict[str, Any]]:
    protocol = reference_protocol()
    failures: list[dict[str, Any]] = []
    for row in night.checks:
        expected = _expected_check(protocol, row)
        verdict = _verdict(row, expected)
        if verdict == "ok":
            continue
        phase, ask = str(row.get("phase")), str(row.get("ask"))
        raised, answered = _quoted(row.get("error")), _quoted(row.get("value"))
        if ask == "gate":
            if "value" in expected:
                continue
            gate = str(row.get("gate"))
            timeout = row.get("timeout")
            if verdict == "thin_details":
                failures.append(_fail(
                    "alert_missing_its_details", phase=phase, asked_for=gate,
                    raised=raised, said=_alert_said(row, expected)))
            elif timeout is not None and float(timeout) <= 0:
                failures.append(_fail(
                    "timeout_sign_not_told_apart", phase=phase, gate=gate,
                    timeout=timeout, raised=raised, expected=str(expected["error"])))
            else:
                failures.append(_fail(
                    "gate_request_outside_its_phase", phase=phase, gate=gate,
                    raised=raised, expected=str(expected["error"])))
        elif phase in protocol.HANDSET_PHASES:
            shared = dict(
                phase=phase,
                case=str(row.get("case")),
                bench=str(row.get("bench")),
                handset=str(row.get("handset")),
                field=ask,
                scope=_execution_scope(
                    phase, row.get("bench"), row.get("case"), row.get("handset")
                ),
            )
            if verdict == "raised_instead":
                failures.append(_fail(
                    "no_handset_reported_inside_its_phase", raised=raised, **shared))
            else:
                failures.append(_fail("wrong_handset_reported", answered=answered, **shared))
        elif verdict == "answered_instead":
            failures.append(_fail(
                "context_answered_outside_its_phase", phase=phase, field=ask, answered=answered))
        elif verdict == "thin_details":
            failures.append(_fail(
                "alert_missing_its_details", phase=phase, asked_for=ask,
                raised=raised, said=_alert_said(row, expected)))
        else:
            failures.append(_fail(
                "context_alert_was_the_wrong_kind", phase=phase, field=ask,
                raised=raised, expected=str(expected["error"])))
    actual = Counter(
        (str(row.get("bench")), str(row.get("phase")), str(row.get("case")),
         str(row.get("handset")), int(row.get("index", -1)), str(row.get("ask")))
        for row in night.checks
    )
    for key in workload.expected_checks(night.spec, inventory()):
        if actual[key]:
            actual[key] -= 1
            continue
        bench, phase, case, handset, index, ask = key
        failures.append(_fail(
            "probe_not_run", bench=bench, phase=phase, case=case,
            handset=handset, index=index, asked_for=ask,
            scope=_execution_scope(phase, bench, case, handset)))
    return failures


def _envelope_failures(night: Night) -> list[dict[str, Any]]:
    protocol = reference_protocol()
    failures: list[dict[str, Any]] = []
    reached = night.benches_reached()
    expected = list(night.benches)
    skipped = [bench for bench in expected if bench not in reached]

    if bool(night.report.get("turns_exhausted")):
        failures.append(_fail(
            "scheduler_turn_limit_exhausted",
            turns=int(night.report.get("turns_taken", 0))))
    unfinished = list(night.report.get("unfinished_at_quiescence", ()))
    if unfinished:
        first = dict(unfinished[0])
        failures.append(_fail(
            "night_left_unfinished_work", unfinished=len(unfinished),
            fiber=_quoted(first.get("fiber")),
            waiting_for=_quoted(first.get("waiting_for"))))

    openings, closings = night.phase_runs(protocol.LAB_OPEN), night.phase_runs(protocol.LAB_CLOSE)
    if closings == 0:
        failures.append(_fail(
            "night_never_closed", stopped_after=reached[-1] if reached else "nothing",
            benches_run=len(reached), benches_expected=len(expected)))
    if skipped:
        failures.append(_fail(
            "benches_after_a_failure_never_ran", bench=reached[-1] if reached else "nothing",
            skipped=len(skipped), skipped_benches=", ".join(skipped)))
    for bench in reached:
        if not night.bench_ran_phase(bench, protocol.BENCH_CLOSE):
            failures.append(_fail(
                "bench_close_skipped", bench=bench,
                handsets=", ".join(night.benches[bench])))

    events: dict[str, list[str]] = defaultdict(list)
    for event in night.report.get("pool", ()):
        events[str(event.get("handset"))].append(str(event.get("action")))
    still_held = {str(item) for item in night.report.get("still_checked_out", ())}
    unbalanced = sorted(handset for ids in night.benches.values() for handset in ids
                        if events[handset] != ["check_out", "release"])
    held = sorted(still_held.intersection(
        handset for ids in night.benches.values() for handset in ids))
    if held:
        failures.append(_fail(
            "handsets_left_checked_out", held=len(held), handsets=", ".join(held),
            bench=str(inventory()[held[0]].bench)))
    if unbalanced:
        handset = unbalanced[0]
        failures.append(_fail(
            "pool_event_order_wrong", handset=handset,
            events=" -> ".join(events[handset]) or "none",
            bench=str(inventory()[handset].bench)))

    opened_at = night.started_at(phase=protocol.LAB_OPEN)
    early = [bench for bench in reached
             if (started := night.started_at(bench=bench)) is not None
             and (opened_at is None or started < opened_at)]
    if early:
        failures.append(_fail(
            "night_opened_out_of_turn", first_bench=early[0], benches_before_opening=len(early),
            openings=openings, benches_run=len(reached)))
    if openings > 1 or closings > 1:
        phase, runs = ((protocol.LAB_OPEN, openings) if openings > 1
                       else (protocol.LAB_CLOSE, closings))
        failures.append(_fail(
            "night_phase_ran_twice", phase=phase, runs=runs, benches_run=len(reached)))
    return failures


def _analyse(report: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    night = Night(report, spec)
    return {
        "attribution_failures": _attribution_failures(night),
        "gate_scope_failures": _gate_scope_failures(night),
        "gate_party_failures": _gate_party_failures(night),
        "context_failures": _context_failures(night),
        "envelope_failures": _envelope_failures(night),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(report: Mapping[str, Any]) -> str:
    'The one line the console shows when a night did not run to the end.'

    reported = str(report.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still going after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(report.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the runner ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the runner ended without saying why"
    return f"the night stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private night against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        spec = workload.build_session(str(PRIVATE_CASE["session"]))
        report = PROJECT.invoke(artifact_dir, {"session": spec})
        if not report.get("ok") or report.get("runner_error"):
            failed_report = dict(report)
            if report.get("runner_error"):
                failed_report["error"] = str(report["runner_error"])
            analysis = dict(failed_analysis(
                _console_error(failed_report), tuple(BUCKETS.values())))
            diagnostic = report.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(report, spec)
        analysis["case"] = {"session": spec["name"], "handsets": len(spec["handsets"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    lab: dict[str, list[str]] = defaultdict(list)
    for handset in inventory().values():
        lab[handset.bench].append(handset.id)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        spec = workload.build_session(record_id) if record_id in PUBLIC_RECORDS else {}
        records.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "handsets": list(spec.get("handsets", ())),
            "benches": workload.benches(spec, inventory()) if spec else {},
            "cases": list(spec.get("case_order", ())),
        })
    return {
        "summary": "The night runner's files, the lab inventory, and the recorded nights.",
        "measurements": {
            "runner_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "harness").glob("*.py")),
            "editable_files": list(EDITABLE_FILES),
            "lab_by_bench": {bench: sorted(ids) for bench, ids in sorted(lab.items())},
        },
        "records": records,
    }


def _meeting_rows(night: Night) -> list[dict[str, Any]]:
    'Every named point the night actually reached, as the console prints it.'

    rows = []
    keys = sorted(set(night.arrivals) | set(night.resumes))
    for key in keys:
        bench, phase, case, gate, index = key
        arrivals = night.arrivals.get(key, [])
        resumes = night.resumes.get(key, [])
        first_resume = min((position for position, _ in resumes), default=None)
        rows.append({
            "bench": bench, "phase": phase, "case": None if case == "None" else case,
            "point": gate, "step_index": index,
            "handsets_on_this_bench": sorted(night.benches.get(bench, ())),
            "arrived": [handset for _, handset in arrivals],
            "resumed": [handset for _, handset in resumes],
            "arrivals_before_the_first_resume": (
                None if first_resume is None
                else sum(1 for position, _ in arrivals if position < first_resume)),
        })
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded night and report the console log.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    spec = workload.build_session(record_id)
    report = PROJECT.invoke(Path(artifact_dir), {"session": spec})
    if not report.get("ok"):
        return {
            "summary": f"The {record_id} night could not run against this runner.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {"execution_error": report.get("error", "unknown failure"),
                       "diagnostic": report.get("diagnostic")},
        }
    night = Night(report, spec)
    return {
        "summary": f"The {record_id} night ran against this runner.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "benches": {bench: list(ids) for bench, ids in night.benches.items()},
            "case_order": list(spec.get("case_order", ())),
            "turns_taken": report.get("turns_taken"),
            "runner_error": report.get("runner_error"),
        },
        "public": {
            "what_each_handset_did": night.steps,
            "named_points": _meeting_rows(night),
            "morning_report": night.records,
            "handset_pool": list(report.get("pool", ())),
            "still_checked_out": list(report.get("still_checked_out", ())),
            "unfinished_at_quiescence": list(report.get("unfinished_at_quiescence", ())),
        },
    }
