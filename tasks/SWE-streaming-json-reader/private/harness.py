'Deterministic, sandboxed analysis of one reader workspace.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import (
    FAMILY_PHRASES,
    PACKET_SIZE_PHRASE,
    SLACK_BYTES,
    build_program,
    driver_events,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("client/reader.py", "client/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-json-reader-",
)


WORKLOAD: Mapping[str, Any] = {"profile": "release", "offset": 29, "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "chunk-boundary-sweep": {"profile": "boundary", "offset": 6, "scale": 0},
    "framing-catalogue": {"profile": "framing", "offset": 11, "scale": 1},
    "slow-producer-trace": {"profile": "flow", "offset": 19, "scale": 1},
    "connection-lifecycle-drill": {"profile": "lifecycle", "offset": 25, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "chunking_invariant_value_stream": "correctness_failures",
    "explicit_framing_rejection": "framing_failures",
    "encoding_contract_fidelity": "encoding_failures",
    "bounded_stream_buffering": "flow_failures",
    "stream_lifecycle_discipline": "lifecycle_failures",
}

_CACHE = AnalysisCache()


def _pass(record: Mapping[str, Any], key: str = "first_pass") -> Mapping[str, Any]:
    value = record.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _readings(count: int) -> str:
    'A count of handed-over values in the words the owner uses for them.'

    return f"{count} reading" if count == 1 else f"{count} readings"


def _where(case: Mapping[str, Any]) -> dict[str, Any]:
    'The part of a failure that says which response it is about.'

    return {
        "label": str(case.get("label")),
        "situation": str(case.get("situation")),
        "content_type": str(case.get("content_type")),
    }


def _ordered(
    failures: Sequence[Mapping[str, Any]], priority: Sequence[str]
) -> list[dict[str, Any]]:
    'Sort a bucket by the order the rubric reports its failure modes in.'

    rank = {kind: index for index, kind in enumerate(priority)}
    return [
        dict(failure)
        for failure in sorted(
            failures, key=lambda item: rank.get(str(item.get("kind")), len(rank))
        )
    ]


CORRECTNESS_PRIORITY = (
    "iteration_raised_unexpectedly",
    "chunk_split_changes_values",
    "values_differ_from_reference",
)


def _correctness_failures(
    records: Sequence[Mapping[str, Any]], program: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    by_family: dict[str, dict[str, Any]] = {}
    for record in records:
        label = str(record.get("label"))
        case = program[label]
        if str(case.get("scenario")) != "chunking":
            continue
        expect = dict(case["expect"])
        outcome = _pass(record)
        family = label.rsplit("-at-", 1)[0]
        seen = by_family.setdefault(family, {"content_type": case["content_type"], "shapes": set()})
        seen["shapes"].add(
            json.dumps(outcome.get("values"), sort_keys=True, ensure_ascii=False)
        )
        if outcome.get("error"):
            failures.append(
                {
                    "kind": "iteration_raised_unexpectedly",
                    **_where(case),
                    "raised": outcome.get("error"),
                    "raised_detail": outcome.get("error_detail"),
                    "packet_sizes": PACKET_SIZE_PHRASE,
                }
            )
            continue
        if outcome.get("values") != expect["values"]:
            delivered = list(outcome.get("values") or ())
            wanted = list(expect["values"] or ())
            failures.append(
                {
                    "kind": "values_differ_from_reference",
                    **_where(case),
                    "observed": (
                        f"handed over {_readings(len(delivered))} where the gateway "
                        f"sent {len(wanted)}"
                    ),
                    "packet_sizes": PACKET_SIZE_PHRASE,
                }
            )
    for family, seen in sorted(by_family.items()):
        if len(seen["shapes"]) > 1:
            failures.append(
                {
                    "kind": "chunk_split_changes_values",
                    "label": family,
                    "situation": f"{FAMILY_PHRASES[family]} at different packet sizes",
                    "content_type": seen["content_type"],
                    "distinct_record_sequences": len(seen["shapes"]),
                    "packet_sizes": PACKET_SIZE_PHRASE,
                }
            )
    return _ordered(failures, CORRECTNESS_PRIORITY)


FRAMING_PRIORITY = (
    "unsupported_media_type_accepted",
    "truncated_body_accepted",
    "trailing_data_accepted",
    "malformed_document_accepted",
    "empty_document_accepted",
    "unframed_sequence_accepted",
    "partial_value_yielded",
    "invalid_record_value_yielded",
    "wrong_error_type",
    "media_type_parameters_mishandled",
    "empty_stream_mishandled",
    "blank_record_mishandled",
)


def _framing_failures(
    records: Sequence[Mapping[str, Any]], program: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        case = program[label]
        if str(case.get("scenario")) != "framing":
            continue
        expect = dict(case["expect"])
        outcome = _pass(record)
        raised = outcome.get("error")
        if expect["error"] is None:
            if raised or outcome.get("values") != expect["values"]:
                failures.append(
                    {
                        "kind": str(expect["refusal"]),
                        **_where(case),
                        "raised": raised,
                        "raised_detail": outcome.get("error_detail"),
                        "observed": (
                            f"refused {case['situation']}"
                            if raised
                            else f"read {case['situation']} but handed over "
                            f"{_readings(len(list(outcome.get('values') or ())))} "
                            f"where the gateway sent {len(list(expect['values'] or ()))}"
                        ),
                    }
                )
            continue
        if raised is None:
            failures.append(
                {
                    "kind": str(expect["accepted"]),
                    **_where(case),
                    "observed": (
                        f"read {case['situation']} without complaint and handed over "
                        f"{_readings(len(list(outcome.get('values') or ())))}"
                    ),
                }
            )
            continue
        if raised != expect["error"]:
            failures.append(
                {
                    "kind": "wrong_error_type",
                    **_where(case),
                    "raised": raised,
                    "raised_detail": outcome.get("error_detail"),
                    "expected": expect["error"],
                    "observed": (
                        f"failed on {case['situation']} with {raised} rather than "
                        f"{expect['error']}"
                    ),
                }
            )
            continue
        delivered = list(outcome.get("values") or ())


        allowed = list(
            expect["prefix_of"] if expect.get("prefix_of") is not None else (expect["prefix"] or [])
        )
        if delivered != allowed[: len(delivered)]:
            failure_mode = str(
                expect.get("yielded") or "partial_value_yielded"
            )
            if failure_mode == "invalid_record_value_yielded":
                observed = (
                    f"handed over {_readings(len(delivered))} from "
                    f"{case['situation']} before reporting the failure, even "
                    "though that record never formed one valid JSON text"
                )
            else:
                observed = (
                    f"handed over {_readings(len(delivered))} out of "
                    f"{case['situation']} before failing, and what came out is "
                    "not what the gateway had written into the intact prefix"
                )
            failures.append(
                {
                    "kind": failure_mode,
                    **_where(case),
                    "record_count": len(delivered),
                    "intact_record_count": len(allowed),
                    "observed": observed,
                }
            )
    return _ordered(failures, FRAMING_PRIORITY)


ENCODING_PRIORITY = (
    "declared_charset_ignored",
    "encoding_detection_wrong",
    "byte_order_mark_mishandled",
    "invalid_charset_mishandled",
)


def _encoding_failures(
    records: Sequence[Mapping[str, Any]], program: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        case = program[label]
        if str(case.get("scenario")) != "encoding":
            continue
        expect = dict(case["expect"])
        outcome = _pass(record)
        raised = outcome.get("error")


        if expect["error"] is not None:
            if raised != expect["error"]:
                failures.append(
                    {
                        "kind": str(expect["fault"]),
                        **_where(case),
                        "raised": raised,
                        "symptom": (
                            "was read and decoded like any other body"
                            if raised is None
                            else f"came back as {raised} rather than the bad-fetch "
                            "failure the collector handles"
                        ),
                    }
                )
            continue
        if raised or outcome.get("values") != expect["values"]:
            failures.append(
                {
                    "kind": str(expect["fault"]),
                    **_where(case),
                    "raised": raised,
                    "raised_detail": outcome.get("error_detail"),
                    "symptom": (
                        f"came back as {raised} with no readings at all"
                        if raised
                        else f"gave us "
                        f"{_readings(len(list(outcome.get('values') or ())))} where the "
                        f"gateway sent {len(list(expect['values'] or ()))}"
                    ),
                }
            )
    return _ordered(failures, ENCODING_PRIORITY)


FLOW_PRIORITY = (
    "flow_read_failed",
    "unmetered_body_access",
    "whole_body_buffered",
    "look_ahead_bound_exceeded",
)


def _flow_failures(
    records: Sequence[Mapping[str, Any]], program: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        case = program[label]
        if str(case.get("scenario")) != "flow":
            continue
        expect = dict(case["expect"])
        outcome = _pass(record)
        if outcome.get("error") or outcome.get("values") != expect["values"]:
            raised = outcome.get("error")
            failures.append(
                {
                    "kind": "flow_read_failed",
                    **_where(case),
                    "raised": raised,
                    "raised_detail": outcome.get("error_detail"),
                    "symptom": (
                        f"came back as {raised} instead of the readings"
                        if raised
                        else f"gave us "
                        f"{_readings(len(list(outcome.get('values') or ())))} where the "
                        f"gateway sent {len(list(expect['values'] or ()))}"
                    ),
                }
            )
            continue
        chunk_size = int(record.get("chunk_size", 1))
        total = int(dict(record.get("stream", {})).get("total_bytes", 0))
        marks = [int(value) for value in outcome.get("bytes_pulled_at_value", ())]
        offsets = [int(value) for value in expect["offsets"] or ()]
        minimum_offsets = [
            int(value)
            for value in (expect.get("minimum_offsets") or expect["offsets"] or ())
        ]
        if len(marks) != len(offsets) or len(minimum_offsets) != len(offsets):
            failures.append(
                {
                    "kind": "flow_read_failed",
                    **_where(case),
                    "raised": None,
                    "symptom": (
                        f"reported {len(marks)} handovers for {_readings(len(offsets))}"
                    ),
                }
            )
            continue
        for position, (mark, minimum, offset) in enumerate(
            zip(marks, minimum_offsets, offsets)
        ):
            if mark < minimum:
                failures.append(
                    {
                        "kind": "unmetered_body_access",
                        **_where(case),
                        "record_position": position,
                        "bytes_pulled": mark,
                        "minimum_bytes": minimum,
                        "observed": (
                            f"handed over reading {position + 1} of {case['situation']} "
                            f"after accounting for {mark} bytes, before the {minimum} "
                            "bytes containing that reading had arrived"
                        ),
                    }
                )
                break
            allowance = offset + chunk_size + SLACK_BYTES
            if mark <= allowance:
                continue
            whole_body = bool(marks) and marks[0] >= total
            failures.append(
                {
                    "kind": "whole_body_buffered" if whole_body else "look_ahead_bound_exceeded",
                    **_where(case),
                    "record_position": position,
                    "bytes_pulled": mark,
                    "allowance": allowance,
                    "body_bytes": total,
                    "slack": f"{SLACK_BYTES} bytes",
                    "observed": (
                        f"pulled the whole body before handing over any reading of "
                        f"{case['situation']}"
                        if whole_body
                        else f"was {mark - allowance} bytes past its budget when it "
                        f"handed over reading {position + 1} of {case['situation']}"
                    ),
                }
            )
            break
    return _ordered(failures, FLOW_PRIORITY)


LIFECYCLE_PRIORITY = (
    "lifecycle_read_failed",
    "stream_read_after_close",
    "stream_not_closed",
    "stream_closed_more_than_once",
    "second_iteration_mishandled",
    "buffered_response_closed",
    "buffered_response_not_repeatable",
    "abandoned_read_drained_body",
)


def _lifecycle_failures(
    records: Sequence[Mapping[str, Any]], program: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        case = program[label]
        outcome = _pass(record)
        stream = dict(record.get("stream", {}))
        streaming = bool(record.get("streaming", True))


        if streaming and int(stream.get("read_after_close", 0)):
            failures.append(
                {
                    "kind": "stream_read_after_close",
                    **_where(case),
                    "observed": (
                        f"the connection was read after it was given back while "
                        f"{case['situation']}"
                    ),
                }
            )
            continue

        closes = int(stream.get("close_count", 0))
        if streaming and closes != 1:
            failures.append(
                {
                    "kind": "stream_not_closed" if closes == 0 else "stream_closed_more_than_once",
                    **_where(case),
                    "close_count": closes,
                    "observed": (
                        f"the connection was never given back while {case['situation']}"
                        if closes == 0
                        else f"the connection was given back "
                        f"{'twice' if closes == 2 else f'{closes} times'} while "
                        f"{case['situation']}"
                    ),
                }
            )
        elif not streaming and closes != 0:
            failures.append(
                {
                    "kind": "buffered_response_closed",
                    **_where(case),
                    "close_count": closes,
                    "observed": (
                        "closed the in-memory response "
                        f"{'once' if closes == 1 else f'{closes} times'} while "
                        f"{case['situation']}"
                    ),
                }
            )

        if str(case.get("scenario")) != "lifecycle":
            continue
        expect = dict(case["expect"])
        if label == "stop-after-the-first-record":
            if outcome.get("error") or not outcome.get("values"):
                failures.append(
                    {
                        "kind": "lifecycle_read_failed",
                        **_where(case),
                        "raised": outcome.get("error"),
                        "raised_detail": outcome.get("error_detail"),
                    }
                )
                continue
            if int(stream.get("bytes_pulled", 0)) >= int(stream.get("total_bytes", 0)):
                failures.append(
                    {
                        "kind": "abandoned_read_drained_body",
                        **_where(case),
                        "bytes_pulled": stream.get("bytes_pulled"),
                        "body_bytes": stream.get("total_bytes"),
                        "observed": (
                            "the whole body had already been pulled by the time the "
                            "caller stopped after the first record"
                        ),
                    }
                )
        elif outcome.get("error") or outcome.get("values") != expect["values"]:
            failures.append(
                {
                    "kind": "lifecycle_read_failed",
                    **_where(case),
                    "raised": outcome.get("error"),
                    "raised_detail": outcome.get("error_detail"),
                }
            )
            continue
        if str(record.get("mode")) == "twice":
            second = _pass(record, "second_pass")
            if streaming:
                raised_again = second.get("error")
                if raised_again != "StreamConsumed":
                    failures.append(
                        {
                            "kind": "second_iteration_mishandled",
                            **_where(case),
                            "raised": raised_again,
                            "observed": (
                                f"{case['situation']} came back with {raised_again} "
                                "instead of saying the body was gone"
                                if raised_again
                                else f"{case['situation']} produced "
                                f"{_readings(len(list(second.get('values') or ())))} "
                                "instead of saying the body was gone"
                            ),
                        }
                    )
            elif second.get("error") or second.get("values") != expect["values"]:
                failures.append(
                    {
                        "kind": "buffered_response_not_repeatable",
                        **_where(case),
                        "raised": second.get("error"),
                        "raised_detail": second.get("error_detail"),
                        "observed": (
                            f"{case['situation']} came back as {second.get('error')} "
                            "on its second pass"
                            if second.get("error")
                            else f"{case['situation']} did not reproduce the gateway's "
                            "readings on its second pass"
                        ),
                    }
                )
    return _ordered(failures, LIFECYCLE_PRIORITY)


def _analyse(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    by_label = {str(case["label"]): dict(case) for case in program}
    records = [
        dict(record)
        for record in candidate.get("records", ())
        if isinstance(record, Mapping)
        and record.get("type") == "read"
        and str(record.get("label")) in by_label
    ]
    return {
        "correctness_failures": _correctness_failures(records, by_label),
        "framing_failures": _framing_failures(records, by_label),
        "encoding_failures": _encoding_failures(records, by_label),
        "flow_failures": _flow_failures(records, by_label),
        "lifecycle_failures": _lifecycle_failures(records, by_label),
        "response_count": len(records),
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private workload once per artifact content and analyse it.'

    def compute() -> Mapping[str, Any]:
        program = build_program(
            str(WORKLOAD["profile"]), int(WORKLOAD["offset"]), int(WORKLOAD["scale"])
        )
        outcome = PROJECT.invoke(artifact_dir, {"events": list(driver_events(program))})
        if not outcome.get("ok"):
            error = str(outcome.get("error", "the reader could not be run"))
            analysis = failed_analysis(
                f"the reader could not be loaded: {error}", tuple(BUCKETS.values())
            )
        else:
            analysis = _analyse(outcome, program)
        return {**analysis, "case": {"profile": str(WORKLOAD["profile"])}}

    return _CACHE.get_or_compute(artifact_dir, compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "artifact_hash": artifact_hash(artifact_dir),
        "project_records": [f"project_records/{path.name}" for path in records],
        "read_ahead_slack_bytes": SLACK_BYTES,
    }


def _gateway_side(expect: Mapping[str, Any]) -> dict[str, Any]:
    "What the gateway sent, in the same shape the build's side is reported."

    if expect.get("error") is not None:
        allowed = expect.get("prefix_of")
        if allowed is None:
            allowed = expect.get("prefix") or []
        return {
            "raised": expect["error"],
            "records_before_the_failure_point": list(allowed),
        }
    values = list(expect.get("values") or [])
    side: dict[str, Any] = {"raised": None, "record_count": len(values), "records": values}
    if expect.get("offsets") is not None:
        side["body_bytes_each_record_needs"] = list(expect["offsets"])
    return side


def _timeline_entry(record: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    outcome = _pass(record)
    values = list(outcome.get("values") or ())
    entry: dict[str, Any] = {
        "label": record.get("label"),
        "situation": case.get("situation"),
        "content_type": record.get("content_type"),
        "transport_chunk_bytes": record.get("chunk_size"),
        "streaming": record.get("streaming"),
        "mode": record.get("mode"),
        "body_bytes": record.get("body_bytes"),
        "the_gateway_sent": _gateway_side(dict(case["expect"])),
        "this_build": {
            "raised": outcome.get("error"),
            "raised_detail": outcome.get("error_detail"),
            "record_count": len(values),
            "records": values,
            "bytes_pulled_at_each_record": outcome.get("bytes_pulled_at_value"),
            "transport": record.get("stream"),
        },
    }
    offsets = dict(case["expect"]).get("offsets")
    if offsets is not None:
        chunk_size = int(record.get("chunk_size", 1))
        entry["read_ahead_budget_at_each_record"] = [
            int(offset) + chunk_size + SLACK_BYTES for offset in offsets
        ]
    if "second_pass" in record:
        second = _pass(record, "second_pass")
        entry["this_build"]["second_read_raised"] = second.get("error")
        entry["this_build"]["second_read_record_count"] = len(
            list(second.get("values") or ())
        )
    return entry


def run_public_record(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded trace against the current workspace.'

    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    program = build_program(str(case["profile"]), int(case["offset"]), int(case["scale"]))
    outcome = PROJECT.invoke(artifact_dir, {"events": list(driver_events(program))})
    if not outcome.get("ok"):
        return {
            "record": record_id,
            "scene": raw.get("scene"),
            "execution_error": (
                "the reader could not be loaded: "
                f"{outcome.get('error', 'the reader could not be run')}"
            ),
        }
    by_label = {str(item["label"]): dict(item) for item in program}
    timeline = [
        _timeline_entry(dict(record), by_label[str(record.get("label"))])
        for record in outcome.get("records", ())
        if isinstance(record, Mapping)
        and record.get("type") == "read"
        and str(record.get("label")) in by_label
    ]
    return {
        "record": record_id,
        "scene": raw.get("scene"),
        "read_ahead_slack_bytes": SLACK_BYTES,
        "responses": timeline,
    }
