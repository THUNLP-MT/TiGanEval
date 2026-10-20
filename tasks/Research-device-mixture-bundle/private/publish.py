'What `run_project` prints: status, one record replayed, one capture request.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import desk, workload, world
from .harness import EDITABLE_FILES, PROJECT, live_receipts, opening_receipts


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "receipt_id", "request_id", "day", "duty_profile", "firmware", "condition",
            "rows_requested", "rows_returned", "credits_charged", "credits_remaining",
            "refusal",
        )
    }


def snapshot(fleet: world.Fleet, record: Mapping[str, Any]) -> dict[str, Any]:
    "One past export and receipt state, read through today's fleet register."

    through = str(record["through_day"])
    context = fleet.context()
    context["as_of"] = str(record["date"])
    context["window"] = dict(context["window"], last_day=through)
    log = context["capture_log"]
    day = list(log["columns"]).index("day")
    context["capture_log"] = {
        "columns": list(log["columns"]),
        "rows": [row for row in log["rows"] if str(row[day]) <= through],
    }
    return context


def _record_receipts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = opening_receipts()["receipts"]
    keep = {str(item) for item in record.get("receipts", ())}
    return [dict(entry) for entry in held if str(entry["receipt_id"]) in keep]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    fleet = workload.current()
    context = fleet.context()
    entries, error = live_receipts(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author", "through_day")},
            }
        )
    units = {profile: 0 for profile in world.PROFILES}
    for unit in fleet.units:
        units[unit.duty_profile] += 1
    return {
        "summary": (
            f"The {context['campaign']} bundle campaign, its annotation terms and the "
            "working records on file."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "fleet": context["fleet"],
            "window": context["window"],
            "as_of": context["as_of"],
            "bundles": context["bundles"],
            "promise_points": context["promise_points"],
            "firmware": context["firmware"],
            "annotation": context["annotation"],
            "units_in_service": sum(units.values()),
            "capture_log_rows": len(context["capture_log"]["rows"]),
            "credits_spent": desk.credits_spent(entries),
            "credits_left": desk.credits_left(fleet, entries),
            "requests_on_file": [_receipt_summary(entry) for entry in entries],
            "receipt_file": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    fleet = workload.current()
    context = snapshot(fleet, record)
    entries = _record_receipts(record)
    run = PROJECT.invoke(
        Path(artifact_dir),
        {
            "contexts": [context],
            "requests": [
                {"kind": "report", "context": 0, "receipts": entries},
                {"kind": "plan", "context": 0, "receipts": entries},
            ],
        },
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_day"),
        "capture_log_rows": len(context["capture_log"]["rows"]),
        "requests_on_file": [_receipt_summary(entry) for entry in entries],
        "credits_spent": desk.credits_spent(entries),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {
                "record": Path(record_path).name,
                "campaign": context["campaign"],
            },
            "public": {
                "session": session,
                "console_error": run.get("error"),
                "diagnostic": run.get("diagnostic"),
            },
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "window": context["window"],
            "credits_spent": desk.credits_spent(entries),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_capture(
    artifact_dir: Path,
    duty_profile: Any,
    firmware: Any,
    condition: Any,
    rows: Any,
    receipt_id: Any,
) -> Mapping[str, Any]:
    return desk.collect(
        Path(artifact_dir), workload.current(), duty_profile, firmware, condition, rows,
        receipt_id,
    )
