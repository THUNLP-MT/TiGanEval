'Deterministic, sandboxed review of one telemetry-uplink workspace.'

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("link/session.py", "link/streams.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-uplink-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "seed": 41, "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "depot-slow-drain": {"profile": "slowdrain", "seed": 11, "scale": 0},
    "field-swap-teardown": {"profile": "teardown", "seed": 19, "scale": 1},
    "nightly-log-upload": {"profile": "upload", "seed": 7, "scale": 1},
    "tuesday-link-silence": {"profile": "silence", "seed": 5, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "frames_the_firmware_accepts": "frame_failures",
    "payload_delivery_is_conserved": "delivery_failures",
    "send_window_bounds_outstanding": "window_failures",
    "stalled_stream_does_not_stop_others": "isolation_failures",
    "teardown_is_two_sided_and_drained": "teardown_failures",
}


TEARDOWN_STEPS = ("close_stream", "peer_close", "present", "probe")


def _teardown_step(step: Mapping[str, Any]) -> bool:
    kind = str(step.get("type"))
    return kind in TEARDOWN_STEPS or (kind == "read" and bool(step.get("after_close")))


REFUSALS: Mapping[str, str] = {
    "a command byte the firmware does not have": "frame_the_firmware_cannot_read",
    "a payload longer than the frame buffer": "frame_over_the_size_cap",
    "a stream id this end is already using": "stream_id_collides_with_the_device",
    "a stream the station never opened": "payload_before_the_stream_is_open",
}

_CACHE = AnalysisCache()
_FROZEN: Any = None


def frozen_protocol() -> Any:
    'The frame contract as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "link" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_frozen_link_protocol", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _FROZEN = module
    return _FROZEN


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the operator console shows it: the directory part of     any path stripped, and a line the owner would not say replaced.'

    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the step ended without saying why"
    return line[:200]


def _failure(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'One row per drill step, with the step that produced it beside it.'

    return [
        {**dict(record), "event": dict(event)}
        for event, record in zip(program, candidate.get("records", ()))
    ]


def _of_type(steps: Sequence[Mapping[str, Any]], *kinds: str) -> list[Mapping[str, Any]]:
    return [step for step in steps if str(step.get("type")) in kinds]


def _phases(steps: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for step in steps:
        phase = str(step.get("phase") or "")
        if phase not in seen:
            seen.append(phase)
    return seen


def _in_phase(steps: Sequence[Mapping[str, Any]], phase: str) -> list[Mapping[str, Any]]:
    return [step for step in steps if str(step.get("phase") or "") == phase]


def _reports(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [step for step in _of_type(steps, "report") if step.get("ok")]


def _rows(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [dict(row) for row in report.get("streams") or ()]


def _last_reports(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    'The closing report of every phase: everything the drill ended up with.'

    last: list[Mapping[str, Any]] = []
    for phase in _phases(steps):
        reports = _reports(_in_phase(steps, phase))
        if reports:
            last.append(reports[-1])
    return last


def _frame_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for report in _last_reports(steps):
        limit = int(report.get("max_frame_size", 0))
        for refused in report.get("frames_the_unit_refused") or ():
            entry = dict(refused)
            reason = str(entry.get("reason", ""))
            kind = REFUSALS.get(reason)
            if kind is None:
                continue
            failures.append(
                _failure(
                    kind,
                    reason=reason,
                    command=str(entry.get("command", "?")),
                    stream=int(entry.get("stream", -1)),
                    payload_bytes=int(entry.get("payload_bytes", 0)),
                    max_frame_size=limit,
                    at=int(entry.get("at", 0)),
                )
            )
    return failures


def _delivery_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = [
        _failure(
            "link_operation_failed",
            label=str(step.get("label")),
            error=_safe_error(step.get("error")),
        )
        for step in steps
        if not step.get("ok")
        and not _teardown_step(step)
        and str(step.get("type")) != "close_session"
    ]
    if failures:
        return failures
    for report in _reports(steps):
        counters = dict(report.get("counters") or {})
        measured = dict(report.get("measured") or {})
        for name in sorted(measured):
            if int(counters.get(name, -1)) != int(measured[name]):
                failures.append(
                    _failure(
                        "link_counter_disagrees_with_link",
                        label=str(report.get("label")),
                        counter=name.replace("_", " "),
                        reported=int(counters.get(name, -1)),
                        measured=int(measured[name]),
                    )
                )
    for report in _last_reports(steps):
        whole = bool(report.get("event", {}).get("expect_delivered"))
        for row in _rows(report):
            handed, arrived = int(row["handed_over"]), int(row["arrived_at_the_unit"])
            if handed and (not row.get("arrived_in_order") or (whole and arrived != handed)):
                failures.append(
                    _failure(
                        "stream_payload_not_delivered",
                        stream=str(row["stream"]),
                        handed_over=handed,
                        arrived=arrived,
                        order=(
                            "matches the handed-over order"
                            if row.get("arrived_in_order")
                            else "does not match the handed-over order"
                        ),
                    )
                )
            pushed, read_here = int(row["sent_by_the_unit"]), int(row["read_here"])
            if pushed and (not row.get("read_in_order") or (whole and read_here != pushed)):
                failures.append(
                    _failure(
                        "inbound_payload_not_delivered",
                        stream=str(row["stream"]),
                        sent_by_the_unit=pushed,
                        read_here=read_here,
                        order=(
                            "matches the unit's order"
                            if row.get("read_in_order")
                            else "does not match the unit's order"
                        ),
                    )
                )
    return failures


def _window_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for report in _last_reports(steps):
        window = int(report.get("send_window", 0))
        for row in _rows(report):
            peak = int(row["peak_standing_at_the_unit"])
            if peak > window:
                failures.append(
                    _failure(
                        "send_window_overrun",
                        stream=str(row["stream"]),
                        peak_standing=peak,
                        send_window=window,
                    )
                )
        if str(report.get("phase")) != "slowdrain":
            continue
        for row in _rows(report):
            if int(row["owed"]) > 0:
                failures.append(
                    _failure(
                        "credited_transfer_never_completes",
                        stream=str(row["stream"]),
                        owed=int(row["owed"]),
                        taken_by_the_unit=int(row["taken_by_the_units_consumer"]),
                    )
                )
    return failures


def _slots(
    steps: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], str | None, dict[str, dict[str, int]]]]:
    'Each radio slot of the phase: the stream it served first, and what every     stream owed and had standing at the unit just before it.'

    handed: dict[str, int] = {}
    emitted: dict[str, int] = {}
    taken: dict[str, int] = {}
    priority: dict[str, int] = {}
    by_id: dict[int, str] = {}
    slots: list[tuple[Mapping[str, Any], str | None, dict[str, dict[str, int]]]] = []
    for step in steps:
        kind = str(step.get("type"))
        label = str(step.get("stream", ""))
        if kind == "open":
            priority[label] = int(step["event"].get("priority", 1))
            by_id[int(step.get("id", -1))] = label
        elif kind == "write":
            handed[label] = int(step.get("handed_over", 0))
        elif kind == "drain":
            taken[label] = taken.get(label, 0) + int(step.get("took", 0))
        elif kind == "pump":
            before = {
                name: {
                    "owed": handed.get(name, 0) - emitted.get(name, 0),
                    "standing": emitted.get(name, 0) - taken.get(name, 0),
                    "priority": priority.get(name, 1),
                }
                for name in handed
            }
            first = next(
                (frame for frame in step.get("frames") or () if str(frame[0]) == "DATA"),
                None,
            )
            served = None if first is None else by_id.get(int(first[1]))
            slots.append((step, served, before))
            for name, delivered in dict(step.get("delivered") or {}).items():
                emitted[name] = emitted.get(name, 0) + int(delivered)
    return slots


def _isolation_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _of_type(steps, "pump"):
        budget = int(step.get("budget", 0))
        wire_bytes = int(step.get("wire_bytes", 0))
        if wire_bytes > budget:
            failures.append(
                _failure(
                    "radio_slot_overrun",
                    slot=str(step.get("label")),
                    wire_bytes=wire_bytes,
                    budget=budget,
                )
            )
    for report in _last_reports(steps):
        if str(report.get("phase")) != "silence":
            continue
        phase = _in_phase(steps, "silence")
        window = int(report.get("send_window", 0))
        pumped = sum(int(row["put_on_the_radio"]) for row in _rows(report))
        if report.get("event", {}).get("expect_ready_complete"):
            for row in _rows(report):
                if not row.get("drains"):
                    continue
                if int(row["put_on_the_radio"]) == 0:
                    failures.append(
                        _failure(
                            "ready_stream_never_advanced",
                            stream=str(row["stream"]),
                            owed=int(row["owed"]),
                            pumped=pumped,
                        )
                    )
                elif int(row["owed"]) > 0:
                    failures.append(
                        _failure(
                            "ready_stream_incomplete_within_budget",
                            stream=str(row["stream"]),
                            owed=int(row["owed"]),
                            pumped=pumped,
                        )
                    )
        for slot, served, before in _slots(phase):
            if served is None or served not in before:
                continue
            state = before[served]
            if state["owed"] <= 0 or state["standing"] >= window:
                continue
            waiting = [
                label
                for label, other in sorted(before.items())
                if other["owed"] > 0
                and other["standing"] < window
                and other["priority"] > state["priority"]
            ]
            if waiting:
                failures.append(
                    _failure(
                        "priority_order_not_served",
                        slot=str(slot.get("label")),
                        served=str(served),
                        waiting=str(waiting[0]),
                    )
                )
    return failures


def _teardown_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = [
        _failure(
            "teardown_operation_failed",
            label=str(step.get("label")),
            error=_safe_error(step.get("error")),
        )
        for step in steps
        if not step.get("ok") and _teardown_step(step)
    ]
    for step in _of_type(steps, "close_session"):
        raised = str(step.get("raised", "nothing"))
        if not step.get("ok") or raised != "nothing":
            failures.append(
                _failure(
                    "close_raised_against_refusing_radio",
                    label=str(step.get("label")),
                    error=_safe_error(step.get("error") or raised),
                )
            )
    if failures:
        return failures
    stream_ids = {
        str(step.get("stream")): int(step.get("id", -1))
        for step in _of_type(steps, "open")
        if step.get("ok")
    }
    for step in _of_type(steps, "pump"):
        expected = str(step.get("event", {}).get("expect_shut", ""))
        if not expected:
            continue
        stream_id = stream_ids.get(expected, -1)
        signaled = any(
            str(frame[0]) == "SHUT" and int(frame[1]) == stream_id
            for frame in step.get("frames") or ()
        )
        if not signaled:
            failures.append(
                _failure(
                    "local_close_not_signaled",
                    stream=expected,
                    slot=str(step.get("label")),
                )
            )
    pushed: dict[str, int] = {}
    read: dict[str, int] = {}
    for step in steps:
        kind = str(step.get("type"))
        label = str(step.get("stream", ""))
        if kind == "peer_push":
            pushed[label] = pushed.get(label, 0) + int(step.get("size", 0))
        elif kind == "read":
            buffered = pushed.get(label, 0) - read.get(label, 0)
            got = int(step.get("read_bytes", 0))
            read[label] = read.get(label, 0) + got
            if step.get("after_close") and got < buffered:
                failures.append(
                    _failure(
                        "buffered_inbound_lost_on_close",
                        stream=label,
                        buffered=buffered,
                        read_back=got,
                    )
                )
        elif kind == "present":


            if step.get("must_be_gone") and step.get("present"):
                failures.append(
                    _failure("stream_left_open_after_teardown", stream=label,
                             at=str(step.get("label")))
                )
            elif step.get("must_be_listed") and not step.get("present"):
                open_end = str(step.get("one_end_open", ""))
                if open_end:
                    failures.append(
                        _failure(
                            "stream_dropped_while_one_end_open",
                            stream=label,
                            at=str(step.get("label")),
                            open_end=open_end,
                        )
                    )
                else:
                    failures.append(
                        _failure("stream_dropped_before_it_was_drained", stream=label,
                                 at=str(step.get("label")),
                                 unread=int(step.get("unread_here", 0)))
                    )
        elif kind == "probe":
            raised = str(step.get("raised", "nothing"))
            if raised != "ClosedLink":
                operation = str(step.get("kind", "operation"))
                failures.append(
                    _failure(
                        "closed_endpoint_accepted_operation",
                        operation=operation,
                        target=label or "the closed link",
                        at=str(step.get("label")),
                        raised=raised,
                    )
                )
    for report in _reports(steps):
        event = dict(report.get("event") or {})
        expected = {str(item) for item in event.get("expect_open") or ()}
        if event.get("expect_open"):
            open_ids = set(int(item) for item in report.get("open_streams") or ())
            actual = {
                str(row["stream"])
                for row in _rows(report)
                if int(row["id"]) in open_ids
            }
            for stream in sorted(expected - actual):
                failures.append(
                    _failure(
                        "unrelated_stream_closed",
                        stream=stream,
                        at=str(report.get("label")),
                    )
                )
            for stream in sorted(actual - expected):
                failures.append(
                    _failure("stream_left_open_after_teardown",
                             stream=stream, at=str(report.get("label")))
                )
        if not event.get("settled"):
            continue
        for ticket in report.get("tickets") or ():
            entry = dict(ticket)
            owed = max(0, int(entry.get("handed_over", 0)) - int(entry.get("delivered", 0)))
            settled = str(entry.get("settled_as", "nothing"))
            if not entry.get("finished") or (owed and settled != "ClosedLink"):
                failures.append(
                    _failure(
                        "pending_write_never_settled",
                        stream=str(entry.get("stream")),
                        owed=owed,
                        settled_as=settled,
                    )
                )
    return failures


def _analyse(candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]) -> dict:
    steps = read_steps(candidate, program)
    return {
        "frame_failures": _frame_failures(steps),
        "delivery_failures": _delivery_failures(steps),
        "window_failures": _window_failures(steps),
        "isolation_failures": _isolation_failures(steps),
        "teardown_failures": _teardown_failures(steps),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the operator console shows when a drill did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the drill box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the link ended without saying why"
    return f"the station stopped part way through the drill: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private drill against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        case = PRIVATE_CASE
        program = build_program(str(case["profile"]), int(case["seed"]), int(case["scale"]))
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        if not candidate.get("ok"):
            error = _console_error(candidate)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"drill": str(case["profile"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
