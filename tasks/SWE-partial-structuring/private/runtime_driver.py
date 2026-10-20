"Sandboxed runner for the provider-ingest simulator: reads one night from stdin, pushes every payload through the workspace's ``ingest.recover.recover``, folds support's corrections through the frozen consumer, prints what came back, and judges nothing.."

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping, Sequence


MEMBERS = ("value", "structured_fields", "failed_fields", "errors", "is_complete")
BLANK = ("value", "structured_fields", "failed_fields", "is_complete", "error_lines", "problem")


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def _names(value: Any) -> list[str] | None:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        return None
    try:
        return sorted(str(item) for item in value)
    except TypeError:
        return None


def _columns(value: Any) -> tuple[dict[str, Any] | None, str]:

    if not hasattr(value, "as_dict"):
        return None, f"the record came back as a {type(value).__name__}"
    try:
        columns = value.as_dict()
    except BaseException as exc:
        return None, _describe(exc)
    if isinstance(columns, Mapping):
        return dict(columns), ""
    return None, f"the record's columns came back as a {type(columns).__name__}"


def _probe(reading: Any) -> dict[str, Any]:
    from ingest import protocol

    probe: dict[str, Any] = dict.fromkeys(BLANK)
    probe["missing_members"] = [name for name in MEMBERS if not hasattr(reading, name)]
    probe["value_state"] = "not_reported"
    if hasattr(reading, "value") and reading.value is None:
        probe["value_state"] = "withheld"
    elif hasattr(reading, "value"):
        columns, problem = _columns(reading.value)
        probe["value_state"] = "published" if columns is not None else "unusable"
        probe["value"], probe["problem"] = columns, problem or None
    for member in ("structured_fields", "failed_fields"):
        if hasattr(reading, member):
            probe[member] = _names(getattr(reading, member))
            if probe[member] is None and probe["problem"] is None:
                probe["problem"] = f"{member} is not a collection of column names"
    flag = getattr(reading, "is_complete", None)
    probe["is_complete"] = bool(flag) if isinstance(flag, (bool, int)) else None
    if hasattr(reading, "errors"):
        try:
            probe["error_lines"] = list(protocol.describe_errors(reading.errors))
        except BaseException as exc:
            probe["problem"] = probe["problem"] or _describe(exc)
    return probe


def _read(payload: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
    from ingest import schema
    from ingest.recover import recover

    try:
        reading = recover(dict(payload), schema.SUBSCRIBER)
    except BaseException as exc:
        return None, {"ok": False, "error": _describe(exc)}
    try:
        return reading, {"ok": True, "error": None, **_probe(reading)}
    except BaseException as exc:
        return reading, {"ok": False, "error": _describe(exc)}


def _publish(drop: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    from ingest import consumer

    ledger = consumer.Ledger()
    try:
        outcome = consumer.publish_drop(list(drop), ledger)
    except BaseException as exc:
        return {"ok": False, "error": _describe(exc), "rows": [], "withheld": [], "tickets": []}
    return {"ok": True, "error": None,
            "rows": [dict(row) for row in ledger.rows],
            "withheld": [dict(item) for item in ledger.withheld],
            "tickets": [dict(item) for item in outcome["tickets"]]}


def _corrections(drop: Sequence[Mapping[str, Any]], programme: Mapping[str, Any]) -> dict[str, Any]:
    from ingest import consumer

    record_id = str(programme["record_id"])
    payload = next(dict(e["payload"]) for e in drop if str(e["record_id"]) == record_id)
    outcome: dict[str, Any] = {"record_id": record_id, "arrangements": {}}
    for name, patches in dict(programme["arrangements"]).items():
        reading, base = _read(payload)
        step: dict[str, Any] = {"ok": base.get("ok", False), "error": base.get("error")}
        if reading is not None:
            try:
                for patch in patches:
                    reading = consumer.apply_correction(reading, dict(patch))
                step.update({"ok": True, "error": None, **_probe(reading)})
            except BaseException as exc:
                step = {"ok": False, "error": _describe(exc)}
        outcome["arrangements"][str(name)] = step
    single = list(dict(programme["arrangements"]).get("single", ()))
    reading, before = _read(payload)
    outcome["base_before"] = before
    outcome["base_after"] = dict(before)
    if reading is not None and single:
        try:
            for patch in single:
                consumer.apply_correction(reading, dict(patch))
            outcome["base_after"] = {"ok": True, "error": None, **_probe(reading)}
        except BaseException as exc:
            outcome["base_after"] = {"ok": False, "error": _describe(exc)}
    split = list(dict(programme["arrangements"]).get("split", ()))
    if len(split) >= 2:
        earlier, _earlier_probe = _read(payload)
        fresh, _fresh_probe = _read(payload)
        try:
            if earlier is None:
                raise RuntimeError("the earlier reading was not produced")
            consumer.apply_correction(earlier, dict(split[0]))
            later = consumer.apply_correction(earlier, dict(split[1]))
            outcome["future_after_discarded_correction"] = {
                "ok": True,
                "error": None,
                **_probe(later),
            }
        except BaseException as exc:
            outcome["future_after_discarded_correction"] = {
                "ok": False,
                "error": _describe(exc),
            }
        try:
            if fresh is None:
                raise RuntimeError("the fresh reading was not produced")
            later = consumer.apply_correction(fresh, dict(split[1]))
            outcome["future_from_fresh_reading"] = {
                "ok": True,
                "error": None,
                **_probe(later),
            }
        except BaseException as exc:
            outcome["future_from_fresh_reading"] = {
                "ok": False,
                "error": _describe(exc),
            }
    return outcome


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    drop = [dict(entry) for entry in payload["drop"]]
    captured = io.StringIO()
    records: list[dict[str, Any]] = []
    with redirect_stdout(captured):
        for entry in drop:
            _reading, probe = _read(dict(entry["payload"]))
            records.append({"record_id": str(entry["record_id"]), **probe})
        publish = _publish([{k: v for k, v in entry.items() if k != "slot"} for entry in drop])
        programme = payload.get("corrections")
        corrections = _corrections(drop, programme) if programme else None
    return {"ok": True, "records": records, "publish": publish,
            "corrections": corrections, "candidate_stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
