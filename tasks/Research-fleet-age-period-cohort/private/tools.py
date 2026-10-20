"What `run_project` prints: the region, a past session's replay, one day."

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import desk, workload, world
from .harness import EDITABLE_FILES, PROJECT, live_receipts, starting_receipts


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "receipt_id", "day", "depot", "builds", "age_band", "vans_asked",
            "vans_returned", "faults_returned", "van_months_returned",
            "walkaround_ref", "days_charged", "days_remaining", "refusal",
        )
    }


def snapshot(region: world.Region, record: Mapping[str, Any]) -> dict[str, Any]:
    'The evidence as it stood at the end of one past working session.'

    through = str(record["through_month"])
    context = region.context()
    context["as_of"] = str(record["date"])
    context["window"]["last_return"] = through
    context["roster"] = [row for row in context["roster"] if row["month"] <= through]
    context["faults"] = [
        row for row in context["faults"] if str(row["raised_date"])[:7] <= through
    ]
    return context


def _record_receipts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = starting_receipts()["entries"]
    keep = {str(item) for item in record.get("receipts", ())}
    return [dict(entry) for entry in held if str(entry["receipt_id"]) in keep]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    region = workload.current()
    context = region.context()
    entries, error = live_receipts(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author", "through_month")},
            }
        )
    return {
        "summary": (
            f"The {context['region']} fleet, the audit's terms and the working records on file."
        ),
        "measurements": {
            "region": context["region"],
            "window": context["window"],
            "as_of": context["as_of"],
            "depots": context["depots"],
            "cards": context["cards"],
            "leases": context["leases"],
            "audit": context["audit"],
            "review": context["review"],
            "vans_on_the_register": len(context["vans"]),
            "faults_on_the_log": len(context["faults"]),
            "days_charged": desk.days_charged(entries),
            "days_left": desk.days_left(region, entries),
            "days_on_the_receipts": [_receipt_summary(entry) for entry in entries],
            "receipts": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    region = workload.current()
    context = snapshot(region, record)
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
        "evidence_through": record.get("through_month"),
        "days_on_the_receipts": [_receipt_summary(entry) for entry in entries],
        "days_charged": desk.days_charged(entries),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "region": context["region"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "region": context["region"],
            "window": context["window"],
            "days_charged": desk.days_charged(entries),
        },
        "public": {
            "session": session,
            "note_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_day(
    artifact_dir: Path,
    depot: Any,
    builds: Any,
    age_band: Any,
    vans: Any,
    day: Any,
    receipt_id: Any,
) -> Mapping[str, Any]:
    return desk.collect(
        Path(artifact_dir), workload.current(), depot, builds, age_band, vans, day, receipt_id
    )
