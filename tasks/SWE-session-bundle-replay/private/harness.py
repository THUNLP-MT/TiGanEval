'Deterministic, sandboxed analysis of one session-bundle workspace.'

from __future__ import annotations

from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import REPLAY_MARKERS, build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("bundle/recorder.py", "bundle/replay.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT, editable_files=EDITABLE_FILES, prefix="tiganeval-bundle-",
    driver=Path(__file__).resolve().with_name("runtime_driver.py"))


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "analysis-handoff": "handoff", "credential-review": "credentials",
    "shared-bundle-review": "shared", "replay-rehearsal": "rehearsal"}

BUCKETS: Mapping[str, str] = {
    "output_attribution": "attribution_failures", "secret_redaction": "redaction_failures",
    "recorder_lifetime": "lifetime_failures", "bundle_admission": "admission_failures",
    "replay_isolation": "replay_failures"}


WORDS: Mapping[str, str] = {
    "stdout": "what the cell printed", "stderr": "the warning line the cell wrote",
    "execute_result": "the value the cell came back with", "metadata": "the file's own header",
    "code": "the line of code the cell ran", "success": "whether the cell worked",
    "execution_count": "the number the cell had", "seq": "the place the entry sits in",
    "error.evalue": "the message the cell raised", "recorded_at": "the time on the entry",
    "error.traceback": "the lines of the traceback"}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None

def reference_protocol() -> Any:
    "The frozen `bundle/protocol.py`, loaded from the project's own tree."
    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "bundle" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_bundle_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the console contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def intended_sessions(program: Mapping[str, Any]) -> tuple[list[dict[str, Any]],
                                                           list[dict[str, Any]]]:
    'The recordings the program asks for, and the starts it asks to be refused.'
    written: set[str] = set()
    recording: dict[str, dict[str, Any]] = {}
    sessions: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    for index, op in enumerate(program.get("operations", ())):
        kind, console = str(op.get("op", "")), str(op.get("console", ""))
        recorder = str(op.get("recorder", "main"))
        if kind == "fixture":
            written.add(str(op["path"]))
        elif kind == "start":
            path = str(op["path"])
            open_session = recording.get(console)
            if open_session is not None or (path in written and not op.get("overwrite")):
                refusals.append({
                    "index": index, "label": str(op["label"]), "console": console, "path": path,
                    "expected": {"recording": open_session is not None,
                                 "path": None if open_session is None else open_session["path"]}})
                continue
            session = {
                "index": index, "label": str(op["label"]), "console": console, "path": path,
                "phase": str(op.get("phase", "")), "cells": [], "recorder": recorder,
                "patterns": tuple(str(item) for item in op.get("redact", ()))}
            recording[console] = session
            sessions.append(session)
        elif kind == "stop":
            session = recording.get(console)
            if session is not None and session["recorder"] == recorder:
                recording.pop(console)
                written.add(session["path"])
        elif kind == "cell":
            session = recording.get(console)
            if session is not None and op.get("store_history", True):
                session["cells"].append(str(op["label"]))
    return sessions, refusals

def reference_cells(program: Mapping[str, Any], protocol: Any) -> dict[str, dict[str, Any]]:
    'Run trusted workload cells in an unobserved console, without candidate hooks.'
    shells: dict[str, Any] = {}
    cells: dict[str, dict[str, Any]] = {}
    for op in program.get("operations", ()):
        kind, console = str(op.get("op", "")), str(op.get("console", ""))
        if kind == "console":
            shells[console] = protocol.Shell(execution_count=int(op.get("execution_count", 1)))
        elif kind == "cell":
            shell = shells[console]
            mark = shell.history.count
            result = shell.run_cell(str(op["code"]), bool(op.get("store_history", True)))
            outputs = protocol.split_outputs(tuple(
                protocol.Output(kind=item.kind, text=item.text, index=position)
                for position, item in enumerate(shell.history.since(mark))
            ))
            event: dict[str, Any] = {
                "type": "cell", "code": str(op["code"]),
                "execution_count": result.execution_count,
                "success": bool(result.success), "stdout": outputs["stdout"],
                "stderr": outputs["stderr"],
                "execute_result": (
                    {"text/plain": outputs["execute_result"]}
                    if outputs["execute_result"] else {}
                ),
            }
            if not result.success and result.error is not None:
                event["error"] = protocol.format_error(result.error)
            cells[str(op["label"])] = event
    return cells

class Run:
    'One run of one program against one delivery, as the checks read it.'
    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.protocol = reference_protocol()
        self.program = program
        self.ops = list(program.get("operations", ()))
        self.records = list(candidate.get("operations", ()))
        self.pairs = list(zip(self.ops, self.records))
        self.by_label = {str(record.get("label")): record for record in self.records}
        self.sessions, self.refusals = intended_sessions(program)
        self.reference_cells = reference_cells(program, self.protocol)
        self.secrets = tuple(str(item) for item in program.get("secrets", ()))
        self.inspections: list[tuple[int, str, Mapping[str, Any]]] = [
            (int(record.get("index", 0)), str(op["path"]), record["file"])
            for op, record in self.pairs
            if str(op.get("op")) == "inspect" and isinstance(record.get("file"), Mapping)]

    def cell(self, label: str) -> Mapping[str, Any]:
        return self.by_label.get(label, {})

    def reference_cell(self, label: str) -> Mapping[str, Any]:
        return self.reference_cells.get(label, {})

    def file_payloads(self, path: str) -> list[Mapping[str, Any]]:
        return [payload for _index, target, payload in self.inspections if target == path]

    def bundle(self, path: str) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]] | None:
        'The metadata and events of the file at `path`, as the console read it.'
        for payload in reversed(self.file_payloads(path)):
            if isinstance(payload.get("events"), list):
                return dict(payload.get("metadata") or {}), list(payload["events"])
        return None

    def reference(self, path: str) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]] | None:
        'What the file at `path` holds, whoever put it there.'
        for op in self.ops:
            if str(op.get("op")) == "fixture" and str(op["path"]) == path:
                return dict(op["metadata"]), [dict(event) for event in op["events"]]
        return self.bundle(path)

    def entries(self, cell_record: Mapping[str, Any]) -> tuple[Any, ...]:
        return tuple(
            self.protocol.Output(kind=str(item["kind"]), text=str(item["text"]), index=position)
            for position, item in enumerate(cell_record.get("printed", ())))

    def expected(self, cell_record: Mapping[str, Any]) -> dict[str, Any]:
        'The entry this cell should have produced, from the frozen reference.'
        return {**self.protocol.split_outputs(self.entries(cell_record)),
                "success": bool(cell_record.get("success")),
                "execution_count": cell_record.get("execution_count")}

    def foreign_text(self, label: str, text: str, expected: str) -> str | None:
        'The other cell whose own output is sitting inside this text.'
        for record in self.records:
            other = str(record.get("label"))
            if str(record.get("op")) != "cell" or other == label:
                continue
            for value in self.protocol.split_outputs(self.entries(record)).values():
                if len(value) >= 6 and value in text and value not in expected:
                    return other
        return None

def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}

def _name(path: str) -> str:
    return Path(str(path)).name

def _int(value: Any, default: int = 0) -> int:
    'A number the desk can quote, whatever the file put in the field.'
    return value if isinstance(value, int) and not isinstance(value, bool) else default

def _read(event: Mapping[str, Any], field: str) -> Any:
    if field == "execute_result":
        result = event.get("execute_result")
        if not isinstance(result, Mapping):
            return result
        return str(result.get("text/plain", "")) if result else ""
    return event.get(field)


def _classify(field: str, expected: Mapping[str, Any], got: Any, label: str, run: Run) -> str:
    text = got if isinstance(got, str) else ""
    if field in ("stdout", "stderr", "execute_result"):
        if run.foreign_text(label, text, str(expected[field])):
            return "outputs_borrowed_from_another_cell"
        if field == "stdout" and expected["execute_result"] and expected["execute_result"] in text:
            return "stdout_carries_the_result"
        if field == "stdout" and expected["stderr"] and expected["stderr"] in text:
            return "stderr_folded_into_stdout"
        if field == "stderr" and expected["stderr"] and not text:
            return "stderr_folded_into_stdout"
    return "recorded_event_does_not_match_the_cell"

def _attribution_failures(run: Run) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for session in run.sessions:
        if session["phase"] != "capture" or session["patterns"]:
            continue
        holding = run.bundle(session["path"])
        if holding is None:
            continue
        events = holding[1]
        by_code: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for event in events:
            by_code[str(event.get("code", ""))].append(event)

        for label in session["cells"]:
            cell = run.cell(label)
            matches = by_code.get(str(cell.get("code", "")), [])
            if not matches:
                continue
            event, expected = matches[0], run.expected(cell)
            for field in ("stdout", "stderr", "execute_result", "success", "execution_count"):
                got = _read(event, field)
                if got == expected[field]:
                    continue
                failures.append(_fail(
                    _classify(field, expected, got, label, run),
                    label=label, seq=_int(event.get("seq")), where=WORDS[field],
                    bundle=_name(session["path"]),
                ))
                break
    return failures


def _lifetime_failures(run: Run) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    protocol = run.protocol
    for session in run.sessions:
        if session["phase"] != "capture" or session["patterns"]:
            continue
        name, expected_labels = _name(session["path"]), list(session["cells"])
        for label in expected_labels:
            actual_record = run.cell(label)
            actual = run.expected(actual_record)
            expected_event = run.reference_cell(label)
            expected = {
                "stdout": str(expected_event.get("stdout", "")),
                "stderr": str(expected_event.get("stderr", "")),
                "execute_result": _read(expected_event, "execute_result"),
                "success": bool(expected_event.get("success")),
                "execution_count": expected_event.get("execution_count"),
            }
            for field in ("stdout", "stderr", "execute_result", "success", "execution_count"):
                if actual[field] == expected[field]:
                    continue
                reported = str(actual_record.get("cell_error") or actual[field])[:120]
                failures.append(_fail(
                    "recording_changed_the_cell", bundle=name, label=label,
                    where=WORDS[field], reported=reported))
                break
        holding = run.bundle(session["path"])
        if holding is None:
            failures.append(_fail(
                "cell_missing_from_the_bundle", bundle=name,
                label=expected_labels[0] if expected_labels else "the first cell",
                cells_recorded=0, cells_run=len(expected_labels)))
            continue
        metadata, events = holding
        counted = Counter(str(event.get("code", "")) for event in events)
        wanted = {str(run.cell(label).get("code", "")): label for label in expected_labels}
        for label in expected_labels:
            code = str(run.cell(label).get("code", ""))
            if counted[code] == 0:
                failures.append(_fail(
                    "cell_missing_from_the_bundle", bundle=name, label=label,
                    cells_recorded=len(events), cells_run=len(expected_labels)))
            elif counted[code] > 1:
                failures.append(_fail(
                    "cell_recorded_twice", bundle=name, label=label, copies=counted[code],
                    cells_recorded=len(events), cells_run=len(expected_labels)))
        unwanted = [code for code in counted if code not in wanted]
        if unwanted:
            stray = next(
                (str(record.get("label")) for record in run.records
                 if str(record.get("op")) == "cell" and str(record.get("code")) == unwanted[0]),
                "an entry nobody ran",
            )
            failures.append(_fail(
                "extra_cell_in_the_bundle", bundle=name, label=stray,
                extra_cells=sum(counted[code] for code in unwanted),
                cells_recorded=len(events), cells_run=len(expected_labels)))
        faults = protocol.schema_errors(metadata, events)
        if faults:
            failures.append(_fail(
                "bundle_the_console_refuses", bundle=name, fault=str(faults[0]),
                faults_found=len(faults), cells_recorded=len(events)))
    for refusal in run.refusals:
        record = run.by_label.get(refusal["label"], {})
        state = dict(record.get("recording") or {})
        expected = refusal["expected"]
        before_hooks = [item.get("hooks") for item in run.records
                        if int(item.get("index", 0)) < refusal["index"]
                        and str(item.get("console") or "") == refusal["console"]
                        and item.get("hooks") is not None]
        attached = bool(before_hooks and before_hooks[-1] != record.get("hooks"))


        disturbed = attached or (
            bool(state.get("recording")) != bool(expected["recording"])
            or (state.get("path") or None) != expected["path"]
        )
        seen = [(index, payload) for index, target, payload in run.inspections
                if target == refusal["path"]]
        before = [payload for index, payload in seen if index < refusal["index"]]
        after = [payload for index, payload in seen if index > refusal["index"]]
        clobbered = bool(before and after
                         and before[-1].get("digest") != after[0].get("digest"))
        if record.get("ok"):
            failures.append(_fail(
                "refused_start_did_not_raise", bundle=_name(refusal["path"]),
                label=refusal["label"],
                reported=str(record.get("returned", "a normal return"))[:120]))
        if disturbed or clobbered:
            holding = run.bundle(refusal["path"])
            changes = []
            if attached:
                changes.append("the console's recording hooks")
            if (
                bool(state.get("recording")) != bool(expected["recording"])
                or (state.get("path") or None) != expected["path"]
            ):
                changes.append("the recorder's reported status")
            if clobbered:
                changes.append("the existing bundle on disk")
            failures.append(_fail(
                "refused_start_changed_the_recording", bundle=_name(refusal["path"]),
                label=refusal["label"], cells_recorded=0 if holding is None else len(holding[1]),
                still_recording=bool(state.get("recording")), changed=", ".join(changes)))
    return failures


def _substituted(value: Any, secrets: Sequence[str], marker: str) -> Any:
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, marker)
        return value
    if isinstance(value, Mapping):
        return {key: _substituted(item, secrets, marker) for key, item in value.items()}
    if isinstance(value, list):
        return [_substituted(item, secrets, marker) for item in value]
    return value

def _leak(event: Mapping[str, Any], secrets: Sequence[str]) -> tuple[str, str] | None:
    error = event.get("error") if isinstance(event.get("error"), Mapping) else {}
    places = (
        ("error.evalue", str(error.get("evalue", ""))),
        ("error.traceback", " ".join(str(line) for line in error.get("traceback", ()) or ())),
        ("stdout", str(event.get("stdout", ""))),
        ("execute_result", str(_read(event, "execute_result") or "")),
        ("stderr", str(event.get("stderr", ""))),
        ("code", str(event.get("code", ""))),
    )
    for field, text in places:
        if any(secret in text for secret in secrets):
            return field, WORDS[field]
    return None

def _reference_events(run: Run, session: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for position, label in enumerate(session["cells"], start=1):
        event = dict(run.reference_cell(str(label)))
        event["seq"] = position
        events.append(event)
    return events

def _first_event_difference(
    expected: Sequence[Mapping[str, Any]], got: Sequence[Mapping[str, Any]]
) -> tuple[int, str] | None:
    for position in range(max(len(expected), len(got))):
        want = expected[position] if position < len(expected) else {}
        actual = got[position] if position < len(got) else {}
        for field in sorted(set(want) | set(actual)):
            if field == "recorded_at":
                continue
            if field in want and field in actual and want[field] == actual[field]:
                continue
            return position, field
    return None

def _structural_metadata_difference(
    run: Run, metadata: Mapping[str, Any], *, event_count: int, pattern_count: int
) -> str | None:
    expected = {
        **run.protocol.console_metadata(),
        "event_count": event_count,
        "redacted_patterns": pattern_count,
    }
    return next((
        key for key in sorted(expected)
        if key not in metadata or metadata[key] != expected[key]
    ), None)

def _redaction_failures(run: Run) -> list[dict[str, Any]]:
    sessions = [session for session in run.sessions if session["phase"] == "credentials"]
    cleaned = next((session for session in sessions if session["patterns"]), None)
    if cleaned is None or not run.secrets:
        return []
    name = _name(cleaned["path"])
    holding = run.bundle(cleaned["path"])
    if holding is None:
        return [_fail("redaction_changed_the_record", bundle=name, seq=0, label="the whole session",
                      where="the file the exporter wrote")]
    metadata, events = holding
    labels = list(cleaned["cells"])
    failures: list[dict[str, Any]] = []
    for position, event in enumerate(events, start=1):
        found = _leak(event, cleaned["patterns"])
        if found is None:
            continue
        field, where = found
        failures.append(_fail(
            "secret_left_in_the_error_text" if field.startswith("error.")
            else "secret_left_in_the_recorded_output",
            bundle=name, seq=_int(event.get("seq"), position), where=where,
            label=labels[position - 1] if position <= len(labels) else f"entry {position}"))
    marker = run.protocol.REDACTION_MARKER
    expected_cleaned = [
        _substituted(event, cleaned["patterns"], marker)
        for event in _reference_events(run, cleaned)
    ]
    difference = _first_event_difference(expected_cleaned, events)
    if difference is not None:
        position, field = difference
        failures.append(_fail(
            "redaction_changed_the_record", bundle=name, seq=position + 1,
            where=WORDS.get(field, f"the {field} of the entry"),
            label=labels[position] if position < len(labels) else f"entry {position + 1}"))
    structural = _structural_metadata_difference(
        run, metadata, event_count=len(expected_cleaned),
        pattern_count=len(cleaned["patterns"]),
    )
    if structural is not None:
        failures.append(_fail(
            "redaction_changed_the_record", bundle=name, seq=0,
            where=f"{WORDS['metadata']} field {structural}", label="the file header"))
    plain = next((session for session in sessions if not session["patterns"]), None)
    holding_plain = None if plain is None else run.bundle(plain["path"])
    if plain is not None and holding_plain is None:
        failures.append(_fail(
            "unprotected_record_was_still_redacted", bundle=_name(plain["path"]), seq=0,
            where="the file the exporter wrote", label="the whole session"))
    elif plain is not None and holding_plain is not None:
        plain_metadata, plain_events = holding_plain
        plain_labels = list(plain["cells"])
        expected_plain = _reference_events(run, plain)
        difference = _first_event_difference(expected_plain, plain_events)
        if difference is not None:
            position, field = difference
            failures.append(_fail(
                "unprotected_record_was_still_redacted", bundle=_name(plain["path"]),
                seq=position + 1, where=WORDS.get(field, f"the {field} of the entry"),
                label=(plain_labels[position] if position < len(plain_labels)
                       else f"entry {position + 1}")))
        plain_structural = _structural_metadata_difference(
            run, plain_metadata, event_count=len(expected_plain), pattern_count=0,
        )
        if plain_structural is not None:
            failures.append(_fail(
                "unprotected_record_was_still_redacted", bundle=_name(plain["path"]), seq=0,
                where=f"{WORDS['metadata']} field {plain_structural}",
                label="the file header"))
        expected_metadata = dict(plain_metadata)


        expected_metadata["created_at"] = metadata.get("created_at")
        expected_metadata["redacted_patterns"] = len(cleaned["patterns"])
        changed_metadata = next((
            key for key in sorted(set(expected_metadata) | set(metadata))
            if key not in expected_metadata or key not in metadata
            or expected_metadata[key] != metadata[key]
        ), None)
        if changed_metadata is not None:
            failures.append(_fail(
                "redaction_changed_the_record", bundle=name, seq=0,
                where=f"{WORDS['metadata']} field {changed_metadata}",
                label="the file header"))
    return failures


def _admission_failures(run: Run) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for op, record in run.pairs:
        if str(op.get("phase")) != "admission" or str(op.get("op")) not in ("load", "replay"):
            continue
        path = str(op["path"])
        reference = run.reference(path)
        if reference is None:
            continue
        codes = tuple(run.protocol.schema_errors(reference[0], reference[1]))
        name, total = _name(path), len(reference[1])
        if str(op["op"]) == "load":
            if codes and record.get("ok"):


                failures.append(_fail("load_admitted_a_faulty_file", bundle=name,
                                      label=str(op["label"]), fault=str(codes[0]),
                                      faults_found=len(codes)))
            elif codes and (
                str(record.get("error", "")).split(":")[0] != "BundleRejected"
                or tuple(record.get("error_codes") or ()) != codes
            ):
                failures.append(_fail(
                    "rejection_did_not_name_the_faults", bundle=name, label=str(op["label"]),
                    reported=str(record.get("error", "nothing at all"))[:120]))
            elif not codes and not record.get("ok"):
                failures.append(_fail("sound_bundle_refused", bundle=name, label=str(op["label"]),
                                      reported=str(record.get("error", "nothing at all"))[:120]))
            continue
        ran = int(record.get("cells_run") or 0)
        if codes and ran >= total:
            failures.append(_fail("edited_bundle_ran_to_the_end", bundle=name,
                                  cells_executed=ran, label=str(op["label"])))
        elif codes and ran:
            failures.append(_fail("edited_bundle_half_ran", bundle=name,
                                  cells_executed=ran, label=str(op["label"])))
        elif not codes and not ran:
            failures.append(_fail("sound_bundle_refused", bundle=name, label=str(op["label"]),
                                  reported=str(record.get("error", "nothing at all"))[:120]))
    return failures


def _replay_failures(run: Run) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for op, record in run.pairs:
        if str(op.get("phase")) != "review" or str(op.get("op")) != "replay":
            continue
        path, name = str(op["path"]), _name(op["path"])
        ran = int(record.get("cells_run") or 0)
        reference = run.reference(path)
        if not ran:

            if reference is not None and not run.protocol.schema_errors(*reference):
                failures.append(_fail(
                    "replay_would_not_open_the_file", bundle=name, label=str(op["label"]),
                    reported=str(record.get("error", "nothing at all"))[:120],
                    counter_before=int(record.get("counter_before") or 0), cells_replayed=0))
            continue
        marker = REPLAY_MARKERS.get(path)
        namespace = dict(record.get("namespace") or {})
        before = int(record.get("counter_before") or 0)
        after = int(record.get("counter_after") or 0)
        failed_at = next(
            (position for position, event in enumerate(reference[1], start=1)
             if event.get("success") is False),
            None,
        ) if reference else None
        total = len(reference[1]) if reference else ran
        expected_ran = failed_at if op.get("stop_on_error", True) and failed_at else total
        if ran != expected_ran:
            failures.append(_fail(
                "replay_cell_count_did_not_match_file", bundle=name, label=str(op["label"]),
                cells_replayed=ran, cells_expected=expected_ran))
        if reference is not None:
            expected_executed = tuple(
                _int(event.get("seq"), position)
                for position, event in enumerate(reference[1][:expected_ran], start=1)
            )
            expected_stopped = (
                _int(reference[1][failed_at - 1].get("seq"), failed_at)
                if failed_at and op.get("stop_on_error", True) else None
            )
            report = record.get("report") if isinstance(record.get("report"), Mapping) else {}
            reported_executed = tuple(report.get("executed") or ())
            reported_stopped = report.get("stopped_at")
            if (reported_executed != expected_executed
                    or reported_stopped != expected_stopped):
                failures.append(_fail(
                    "replay_report_did_not_match_execution", bundle=name,
                    label=str(op["label"]), cells_replayed=ran,
                    reported=json.dumps(dict(report), sort_keys=True)[:120]))
        if marker is not None:
            name_of, stopped_value, through_value = marker
            if op.get("stop_on_error", True) and namespace.get(name_of) != stopped_value:
                failures.append(_fail(
                    "replay_ran_past_the_failed_cell", bundle=name, label=str(op["label"]),
                    cells_after_the_failure=max(ran - (failed_at or total), 0),
                    cells_replayed=ran))
            elif not op.get("stop_on_error", True) and namespace.get(name_of) != through_value:
                failures.append(_fail(
                    "replay_stopped_at_a_cell_it_should_have_run", bundle=name,
                    label=str(op["label"]), cells_replayed=ran))
        if op.get("store_history", True):
            if after - before != expected_ran:
                failures.append(_fail(
                    "replay_took_the_recorded_numbering", bundle=name, label=str(op["label"]),
                    counter_before=before, counter_after=after, cells_replayed=ran))
        elif after != before:
            failures.append(_fail(
                "quiet_replay_numbered_the_console", bundle=name, label=str(op["label"]),
                counter_before=before, counter_after=after, cells_replayed=ran))
    return failures

def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    run = Run(candidate, program)
    return {"attribution_failures": _attribution_failures(run),
            "redaction_failures": _redaction_failures(run),
            "lifetime_failures": _lifetime_failures(run),
            "admission_failures": _admission_failures(run),
            "replay_failures": _replay_failures(run)}


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"

def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a session did not finish.'
    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the console ended without saying why"
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the console ended without saying why"
    return f"the console stopped part way through the session: {line[:200]}"

def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private session against this workspace and bucket what went wrong.'
    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"session": "release", "operations": len(program["operations"])}
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
        program = build_program(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else {}
        operations = list(program.get("operations", ()))
        records.append({
            "record": f"project_records/{path.name}", "scene": raw.get("scene"),
            "operations": len(operations),
            "consoles": sorted({str(op["console"]) for op in operations if op.get("console")}),
            "files": sorted({str(op["path"]) for op in operations if op.get("path")})})
    return {
        "summary": "The console workspace and the sessions the desk replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root), "editable_files": list(EDITABLE_FILES),
            "package_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "bundle").glob("*.py")),
            "sample_files": sorted(
                f"{path.relative_to(root).as_posix()} ({path.stat().st_size} bytes)"
                for path in (root / "samples").glob("*"))},
        "records": records}

def _operation_rows(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Every operation the console performed, and what it did.'
    keep = ("printed", "counter", "execution_count", "success", "cell_error", "recorder_name",
            "returned", "recording", "hooks", "console_counter", "file", "loaded", "report",
            "counter_before", "counter_after", "cells_run", "namespace", "error_codes")
    rows = []
    for record in candidate.get("operations", ()):
        row = {"label": record.get("label"), "operation": record.get("op"),
               "console": record.get("console"), "completed": bool(record.get("ok")),
               "error": record.get("error")}
        row.update({key: record[key] for key in keep if key in record})
        rows.append(row)
    return rows

def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded session and report what the console did.'
    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} session could not run against these files.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {"execution_error": candidate.get("error", "unknown failure"),
                       "diagnostic": candidate.get("diagnostic")}}
    return {
        "summary": f"The {record_id} session ran against these files.",
        "measurements": {"record_id": record_id, "scene": raw.get("scene"),
                         "operation_count": len(candidate.get("operations", ())),
                         "console_output": candidate.get("stdout", "")},
        "public": {"what_the_console_did": _operation_rows(candidate)}}
