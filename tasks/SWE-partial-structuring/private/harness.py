"Deterministic, sandboxed measurement of one night's provider drop."

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    CANDIDATE_FAILURE,
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
)

from .workload import build_case, expected_after, expected_reading


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("ingest/recover.py", "ingest/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-provider-ingest-",
    timeout=60.0,
)


PRIVATE_WORKLOAD: Mapping[str, Any] = {"profile": "nightly", "seed": 61, "scale": 2}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "feed-2026-08-12": {"profile": "abort", "seed": 12, "scale": 1},
    "feed-2026-08-14": {"profile": "provenance", "seed": 14, "scale": 1},
    "order-2026-08-19": {"profile": "orders", "seed": 19, "scale": 1},
    "corrections-2026-08-15": {"profile": "console", "seed": 15, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "field_provenance_accounting": "accounting_failures",
    "publishable_or_withheld": "publication_failures",
    "diagnosis_matches_the_strict_reading": "diagnosis_failures",
    "nested_and_collection_recovery": "recovery_failures",
    "corrections_fold_into_the_reading": "correction_failures",
}


ARRANGEMENTS: Mapping[str, str] = {
    "single": "in one message",
    "split": "as two separate messages",
    "repeated": "with the columns that had already read repeated in it",
}

_BLOCK_COLUMNS = ("address", "lines")
_CACHE = AnalysisCache()


def _protocol():
    from ..workspace.ingest import protocol

    return protocol


def _schema():
    from ..workspace.ingest import schema

    return schema


def _payload_for(profile: str, seed: int, scale: int) -> tuple[dict[str, Any], dict[str, Any]]:
    case = build_case(profile, seed, scale)
    payload = {
        "drop": [{"record_id": e["record_id"], "payload": e["payload"]} for e in case["drop"]],
        "corrections": case["corrections"],
    }
    return payload, case


_PROCESS_DEATH_PREFIXES = ("candidate process exited", "candidate returned")


def _reportable_error(error: str) -> str:
    'The failure text the owner reads off a replay that produced no reading.'

    text = str(error).strip()
    if text.startswith(_PROCESS_DEATH_PREFIXES):
        return "the ingest died before it read anything"
    return text


def _stub_analysis(error: str) -> dict[str, Any]:
    failure = {"kind": CANDIDATE_FAILURE, "record_id": "the first payload in the drop",
               "error": _reportable_error(error)}
    analysis: dict[str, Any] = {"harness_error": str(error), "records": []}
    for bucket in BUCKETS.values():
        analysis[bucket] = [dict(failure)]
    return analysis


def _sets(probe: Mapping[str, Any]) -> tuple[set[str] | None, set[str] | None]:
    structured, failed = probe.get("structured_fields"), probe.get("failed_fields")
    return (set(structured) if isinstance(structured, list) else None,
            set(failed) if isinstance(failed, list) else None)


def _add(out: list, kind: str, record_id: str, **fields: Any) -> None:
    out.append({"kind": kind, "record_id": str(record_id), **fields})


def _mapping(value: Any) -> dict[str, Any]:
    'A published record read as columns, whatever the reading put there: a     reading may hand the publisher something that is not a block at all, and     that is a project failure to report, never a measurement that may raise..'

    return dict(value) if isinstance(value, Mapping) else {}


def _column_of(block: Any, name: str) -> str:
    'One line of a published address block, as the owner reads it off a row.'

    if isinstance(block, Mapping):
        held = block.get(name)
        if isinstance(held, (str, int, float)) and not isinstance(held, bool):
            return str(held)
    return "nothing at all"


def _line_count(value: Any) -> int:
    return len(value) if isinstance(value, (list, tuple)) else 0


def _accounting(record_id, payload, probe, expected, protocol, record, out) -> None:
    structured, failed = _sets(probe)
    if structured is None or failed is None or probe.get("is_complete") is None:
        missing = probe.get("missing_members") or []
        problem = (f"the reading carries no {missing[0]}" if missing
                   else str(probe.get("problem") or "the reading carries no list of columns"))
        _add(out, "field_accounting_not_reported", record_id, problem=problem)
        return
    names = set(protocol.field_names(record))
    derived = set(protocol.derived_names(record))
    for spec in protocol.init_fields(record):
        if spec.kind != "scalar" or spec.name not in expected["failed"]:
            continue
        if spec.name in failed:
            continue


        if spec.name not in structured:
            continue
        kind = ("absent_column_reported_as_provider_data" if spec.name not in payload
                else "fallback_value_reported_as_provider_data")
        _add(out, kind, record_id, column=spec.name)
        return


    stray = sorted((structured | failed) & derived)
    if stray:
        _add(out, "derived_column_in_the_accounting", record_id, column=stray[0])
        return
    both = sorted(structured & failed)
    if both:
        _add(out, "supplied_column_on_both_lists", record_id, column=both[0])
        return
    outside = sorted((structured | failed) - names - derived)
    if outside:
        _add(out, "name_that_is_not_a_column_of_the_file", record_id, column=outside[0])
        return
    unlisted = sorted(names - structured - failed)
    if unlisted:
        _add(out, "supplied_column_on_neither_list", record_id, column=unlisted[0])
        return
    clean = sorted(failed & set(expected["structured"]))
    if clean:
        _add(out, "clean_column_reported_as_a_gap", record_id, column=clean[0])
        return
    if bool(probe["is_complete"]) and failed:
        _add(out, "read_whole_although_the_ticket_has_columns_on_it", record_id,
             column=sorted(failed)[0], columns_on_the_ticket=len(failed))
    elif not bool(probe["is_complete"]) and not failed:
        _add(out, "not_read_whole_although_the_ticket_is_empty", record_id,
             columns_the_file_gave_us=len(structured))


def _withheld(record_id, expected, out) -> None:
    'A record the contract can publish and the reading did not: short of     columns we all carry standby values for, or short of nothing at all.'

    if expected["failed"]:
        _add(out, "record_withheld_although_every_gap_has_a_fallback", record_id,
             columns_with_a_fallback=len(expected["failed"]))
    else:
        _add(out, "record_withheld_although_nothing_is_missing", record_id,
             columns_the_file_gave_us=len(expected["structured"]))


def _publication(record_id, probe, expected, protocol, record, out) -> None:
    state = str(probe.get("value_state"))
    if expected["value"] is None:


        gaps = sorted(
            name for name in expected["failed"]
            if record.field(name).default is protocol.MISSING
        )
        if state == "published" and gaps:
            _add(out, "record_published_without_a_required_column", record_id, column=gaps[0])
        return
    if state == "withheld":
        _withheld(record_id, expected, out)
        return
    if state != "published":
        _add(out, "published_column_holds_neither_the_file_nor_the_fallback", record_id,
             column="the record itself")
        return
    published = _mapping(probe.get("value"))
    reference = expected["value"].as_dict()
    for spec in protocol.init_fields(record):
        if spec.name in _BLOCK_COLUMNS:
            continue
        if published.get(spec.name) != reference.get(spec.name):
            _add(out, "published_column_holds_neither_the_file_nor_the_fallback", record_id,
                 column=spec.name, published=published.get(spec.name),
                 the_file_or_the_fallback=reference.get(spec.name))
            return


    for spec in record.fields:
        if spec.init:
            continue
        if published.get(spec.name) != reference.get(spec.name):
            _add(out, "computed_column_does_not_match_the_record", record_id,
                 column=spec.name, published=published.get(spec.name),
                 the_record_gives=reference.get(spec.name))
            return


def _diagnosis(record_id, probe, expected, protocol, out) -> None:
    lines = probe.get("error_lines")
    if not isinstance(lines, list):
        _add(out, "diagnosis_not_reported", record_id,
             problem=str(probe.get("problem") or "the reading carries no problems at all"))
        return


    reported = Counter(str(line) for line in lines)
    wanted = Counter(expected["lines"])
    absent_column = sorted(
        line for line in wanted - reported
        if line.startswith(protocol.MISSING_FIELD_MESSAGE)
    )
    if absent_column:
        _add(out, "absent_column_produces_no_line", record_id, line=absent_column[0])
        return
    missing = sorted(wanted - reported)
    if missing:
        _add(out, "line_missing_from_the_diagnosis", record_id, line=missing[0])
        return
    extra = sorted(line for line in reported - wanted if line not in wanted)
    if extra:
        _add(out, "line_the_strict_reading_does_not_give", record_id, line=extra[0])
        return
    repeated = sorted(line for line in reported - wanted if line in wanted)
    if repeated:
        _add(out, "the_same_line_twice_on_the_ticket", record_id,
             line=repeated[0], times_on_the_ticket=reported[repeated[0]])


def _recovery(record_id, probe, expected, record, out) -> None:
    structured, _failed = _sets(probe)
    if structured is not None:
        confirmed = sorted(
            name for name in _BLOCK_COLUMNS if name in structured and name in expected["failed"]
        )
        if confirmed:
            _add(out, "recovered_block_reported_as_provider_data", record_id,
                 column=confirmed[0])
            return
    if str(probe.get("value_state")) != "published":
        return
    published = _mapping(probe.get("value"))
    reference = {
        name: _plain(expected["field_values"].get(name)) for name in _BLOCK_COLUMNS
    }
    block = published.get("address")
    if block != reference["address"]:


        if block == _plain(record.field("address").default):
            _add(out, "nested_block_discarded_although_part_of_it_read", record_id,
                 line1=_column_of(block, "line1"))
        else:
            _add(out, "published_block_is_not_the_block_the_file_gave_us", record_id,
                 postcode=_column_of(block, "postcode"))
        return
    if published.get("lines") != reference["lines"]:
        _add(out, "published_list_does_not_match_the_file", record_id,
             published_line_count=_line_count(published.get("lines")),
             line_count_the_reading_owes=_line_count(reference["lines"]))


def _plain(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _corrections(case, candidate, record, out) -> None:
    programme = case.get("corrections")
    outcome = candidate.get("corrections")
    if not programme or not isinstance(outcome, Mapping):
        _add(out, "corrections_not_folded_into_the_reading",
             str((programme or {}).get("record_id", "the corrected account")),
             problem="the correction round produced nothing at all")
        return
    record_id = str(programme["record_id"])
    payload = next(dict(entry["payload"])
                   for entry in case["drop"] if str(entry["record_id"]) == record_id)
    base = dict(outcome.get("base_before") or {})
    steps = dict(outcome.get("arrangements") or {})
    ends: dict[str, Any] = {}
    for name in ARRANGEMENTS:
        if name not in programme["arrangements"]:
            continue
        step = dict(steps.get(name) or {})
        if not step.get("ok") or step.get("error"):
            _add(out, "corrections_not_folded_into_the_reading", record_id,
                 problem=str(step.get("error") or "the correction was never folded in"))
            return
        ends[name] = step
    supplied = set(_protocol().field_names(record))
    base_structured, _base_failed = _sets(base)
    if base_structured is not None:
        base_structured = base_structured & supplied
    base_value = dict(base.get("value") or {})


    before = expected_reading(payload, record)["value"]
    from_the_file = before.as_dict() if before is not None else {}
    for name, step in ends.items():
        arrangement = ARRANGEMENTS[name]
        patches = list(programme["arrangements"][name])
        sent = {str(key) for patch in patches for key in dict(patch)}
        after, after_failed = _sets(step)
        if after is not None:
            after = after & supplied
        wanted = expected_after(payload, patches, record)
        if base_structured is not None and after is not None:
            lost = sorted(base_structured - after)
            if lost:
                _add(out, "correction_lost_a_column_that_had_already_read", record_id,
                     column=lost[0], arrangement=arrangement)
                return
        published = _mapping(step.get("value"))
        for column in sorted(base_structured or ()):
            if column not in published:
                _add(out, "correction_lost_a_column_that_had_already_read", record_id,
                     column=column, arrangement=arrangement)
                return
            if column not in from_the_file:
                continue
            moved = published[column] != base_value.get(column)
            if moved and published[column] != from_the_file[column]:
                _add(out, "correction_overwrote_a_column_that_had_already_read", record_id,
                     column=column, arrangement=arrangement)
                return
        if wanted["value"] is not None and str(step.get("value_state")) != "published":
            _add(out, "correction_left_the_record_unpublishable", record_id,
                 arrangement=arrangement)
            return


        gaps = sorted(((after_failed or set()) & supplied) - set(wanted["failed"]))
        if gaps:
            _add(out, "corrected_reading_still_shows_the_column_as_a_gap", record_id,
                 column=gaps[0], arrangement=arrangement)
            return
        reference = wanted["value"].as_dict() if wanted["value"] is not None else {}
        wrong = sorted(
            column
            for column in set(wanted["structured"]) & sent
            if published.get(column) != reference.get(column)
        )
        if wrong:
            _add(out, "corrected_record_does_not_hold_what_support_sent", record_id,
                 column=wrong[0], arrangement=arrangement)
            return
    reference_end = ends.get("single")
    for name, step in ends.items():
        if name == "single" or reference_end is None:
            continue
        if _end_state(step) != _end_state(reference_end):
            _add(out, "correction_outcome_depends_on_how_it_arrives", record_id,
                 arrangement=ARRANGEMENTS[name])
            return
    after = dict(outcome.get("base_after") or {})
    if _end_state(after) != _end_state(base):
        changed = "the reading's reported state"
        if after.get("value") != base.get("value"):
            changed = "the record it publishes"
        elif after.get("structured_fields") != base.get("structured_fields"):
            changed = "the list of columns it holds as the provider's"
        elif after.get("failed_fields") != base.get("failed_fields"):
            changed = "the columns on its ticket"
        elif after.get("is_complete") != base.get("is_complete"):
            changed = "whether it is marked read whole"
        elif after.get("error_lines") != base.get("error_lines"):
            changed = "the lines on its ticket"
        _add(out, "the_earlier_reading_changed_when_the_correction_arrived", record_id,
             member=changed)
        return
    if "split" in programme["arrangements"]:
        after_discarded = dict(
            outcome.get("future_after_discarded_correction") or {}
        )
        from_fresh = dict(outcome.get("future_from_fresh_reading") or {})
        if not after_discarded.get("ok") or not from_fresh.get("ok"):
            problem = (
                after_discarded.get("error")
                or from_fresh.get("error")
                or "the later correction produced no reading"
            )
            _add(out, "corrections_not_folded_into_the_reading", record_id,
                 problem=str(problem))
            return
        if _end_state(after_discarded) != _end_state(from_fresh):
            _add(out, "the_earlier_reading_changed_when_the_correction_arrived",
                 record_id, member="what a later correction produces from it")


def _end_state(step: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        step.get("value_state"),
        json.dumps(step.get("value"), sort_keys=True, default=str),
        tuple(step.get("structured_fields") or ()),
        tuple(step.get("failed_fields") or ()),
        step.get("is_complete"),
        tuple(step.get("error_lines") or ()),
    )


def _analyse(candidate: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    protocol = _protocol()
    record = _schema().SUBSCRIBER
    accounting: list[dict[str, Any]] = []
    publication: list[dict[str, Any]] = []
    diagnosis: list[dict[str, Any]] = []
    recovery: list[dict[str, Any]] = []
    correction: list[dict[str, Any]] = []
    probes = {
        str(item.get("record_id")): dict(item) for item in candidate.get("records", ())
    }
    for entry in case["drop"]:
        record_id = str(entry["record_id"])
        payload = dict(entry["payload"])
        expected = expected_reading(payload, record)
        probe = probes.get(record_id)
        if probe is None or not probe.get("ok"):
            problem = str((probe or {}).get("error") or "the ingest returned no reading")
            _add(accounting, "field_accounting_not_reported", record_id, problem=problem)
            _add(diagnosis, "diagnosis_not_reported", record_id, problem=problem)
            if expected["value"] is not None:
                _withheld(record_id, expected, publication)
            continue
        _accounting(record_id, payload, probe, expected, protocol, record, accounting)
        _publication(record_id, probe, expected, protocol, record, publication)
        _diagnosis(record_id, probe, expected, protocol, diagnosis)
        _recovery(record_id, probe, expected, record, recovery)
    publish = candidate.get("publish")
    if not isinstance(publish, Mapping) or not publish.get("ok"):
        _add(
            publication,
            "publisher_failed_during_the_drop",
            "the nightly drop",
            error=str(
                ((publish or {}).get("error") or
                 "the publisher returned no completed result")
                if isinstance(publish, Mapping)
                else "the publisher returned no result"
            ),
        )
    _corrections(case, candidate, record, correction)
    return {
        "accounting_failures": accounting,
        "publication_failures": publication,
        "diagnosis_failures": diagnosis,
        "recovery_failures": recovery,
        "correction_failures": correction,
        "records": list(candidate.get("records", ()))[:4],
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private night once against this workspace and measure it.'

    def compute() -> Mapping[str, Any]:
        payload, case = _payload_for(
            str(PRIVATE_WORKLOAD["profile"]),
            int(PRIVATE_WORKLOAD["seed"]),
            int(PRIVATE_WORKLOAD["scale"]),
        )
        outcome = PROJECT.invoke(artifact_dir, payload)
        if not outcome.get("ok"):
            analysis = _stub_analysis(str(outcome.get("error", "the ingest could not be run")))
        else:
            analysis = _analyse(outcome, case)
        return {
            **analysis,
            "case": {
                "profile": str(PRIVATE_WORKLOAD["profile"]),
                "payloads_in_the_drop": len(case["drop"]),
            },
        }

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    protocol = _protocol()
    record = _schema().SUBSCRIBER
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": "The ingest workspace and the recorded drops are available.",
        "measurements": {
            "workspace_hash": artifact_hash(artifact_dir),
            "project_records": [f"project_records/{path.name}" for path in records],
            "columns_the_contract_declares": list(protocol.field_names(record)),
            "columns_with_a_fallback": [
                spec.name
                for spec in protocol.init_fields(record)
                if spec.default is not protocol.MISSING
            ],
            "columns_the_ingest_computes": list(protocol.derived_names(record)),
            "unrecognised_keys_are_read_as_problems": bool(record.closed),
        },
        "observed": {},
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case_spec = PUBLIC_RECORDS[record_id]
    payload, case = _payload_for(
        str(case_spec["profile"]), int(case_spec["seed"]), int(case_spec["scale"])
    )
    outcome = PROJECT.invoke(artifact_dir, payload)
    if not outcome.get("ok"):
        return {
            "summary": "The recorded drop could not be run against this workspace.",
            "measurements": {"record_id": record_id, "payloads": len(case["drop"])},
            "observed": {"execution_error": outcome.get("error", "unknown failure")},
        }
    record = _schema().SUBSCRIBER
    probes = {str(item.get("record_id")): dict(item) for item in outcome.get("records", ())}
    publish = dict(outcome.get("publish") or {})
    rows = {str(row.get("record_id")): dict(row) for row in publish.get("rows", ())}
    tickets = {str(item.get("record_id")): dict(item) for item in publish.get("tickets", ())}
    held = {str(item.get("record_id")): dict(item) for item in publish.get("withheld", ())}
    timeline = []
    for entry in case["drop"]:
        payload_id = str(entry["record_id"])
        probe = probes.get(payload_id, {})
        row = rows.get(payload_id, {})
        keys = dict(entry["payload"])
        line = {
            "record_id": payload_id,
            "payload_keys": sorted(str(key) for key in keys),
            "payload_line_count": len(keys["lines"]) if isinstance(keys.get("lines"), list) else None,
            "reading_returned": bool(probe.get("ok")),
            "reading_error": probe.get("error"),
            "record_state": probe.get("value_state"),
            "published_columns": probe.get("value"),
            "columns_held_as_the_provider_s": probe.get("structured_fields"),
            "columns_on_the_ticket": probe.get("failed_fields"),
            "read_whole": probe.get("is_complete"),
            "lines_the_reading_produced": probe.get("error_lines"),
            "ledger_confirmed_columns": row.get("confirmed_columns"),
            "ledger_null_columns": row.get("null_columns"),
            "ledger_published_line_count": row.get("published_line_count"),
            "ledger_invoice_pence": row.get("invoice_pence"),
            "ticket": tickets.get(payload_id),
            "withheld": held.get(payload_id),
        }
        if record_id == "feed-2026-08-12":
            line["lines_the_nightly_pipeline_raised"] = list(
                expected_reading(dict(entry["payload"]), record)["lines"]
            )
        timeline.append(line)
    measurements: dict[str, Any] = {
        "record_id": record_id,
        "payloads_in_the_drop": len(case["drop"]),
        "rows_written_to_the_ledger": len(publish.get("rows", ())),
        "rows_held_back": len(publish.get("withheld", ())),
        "tickets_opened": len(publish.get("tickets", ())),
        "publisher_ran": bool(publish.get("ok")),
        "publisher_error": publish.get("error"),
    }
    observed: dict[str, Any] = {"drop": timeline}
    corrections = outcome.get("corrections")
    if isinstance(corrections, Mapping):
        step = dict(dict(corrections.get("arrangements") or {}).get("single") or {})
        observed["correction_round"] = {
            "record_id": corrections.get("record_id"),
            "patch": list(case["corrections"]["arrangements"]["single"]),
            "before": {
                key: dict(corrections.get("base_before") or {}).get(key)
                for key in ("value_state", "structured_fields", "failed_fields", "is_complete")
            },
            "after": {
                key: step.get(key)
                for key in ("ok", "error", "value_state", "structured_fields", "failed_fields", "is_complete")
            },
        }
    return {
        "summary": "The recorded drop ran against this workspace.",
        "measurements": measurements,
        "observed": observed,
    }
