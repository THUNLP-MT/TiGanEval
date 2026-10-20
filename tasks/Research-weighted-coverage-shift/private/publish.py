'What `run_project` prints: the depot as it stands, one past session replayed, and one night booked.'

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
            "receipt_id", "visit_id", "week", "job_class", "jobs_requested",
            "jobs_returned", "units_charged", "roster_ok", "refusal", "units_remaining",
        )
    }


def snapshot(depot: world.Depot, record: Mapping[str, Any]) -> dict[str, Any]:
    'The evidence as it stood at the end of one past working session.'

    through = int(record["through_week"])
    context = depot.context()
    context["as_of"] = str(record["date"])
    context["audit"]["weeks"] = [week for week in depot.weeks() if week <= through]
    context["intake_log"] = [row for row in context["intake_log"] if row["week"] <= through]
    context["sheets"] = [row for row in context["sheets"] if row["week"] <= through]
    return context


def _record_receipts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = opening_receipts()["receipts"]
    keep = {str(item) for item in record.get("receipts", ())}
    return [dict(entry) for entry in held if str(entry["receipt_id"]) in keep]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    depot = workload.current()
    context = depot.context()
    receipts, error = live_receipts(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author", "through_week")},
            }
        )
    return {
        "summary": (
            f"The {context['depot']} dispatch board, its audit terms and the working "
            "records on file."
        ),
        "measurements": {
            "depot": context["depot"],
            "month": context["month"],
            "as_of": context["as_of"],
            "board": {
                "hold_rule": context["board"]["hold_rule"],
                "window_limit_minutes": context["board"]["window_limit_minutes"],
            },
            "audit": context["audit"],
            "visits": context["visits"],
            "traffic": context["traffic"],
            "sheets_on_file": len(context["sheets"]),
            "units_spent": desk.units_spent(receipts),
            "units_left": desk.units_left(depot, receipts),
            "visits_on_the_receipts": [_receipt_summary(entry) for entry in receipts],
            "receipts": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    depot = workload.current()
    context = snapshot(depot, record)
    receipts = _record_receipts(record)
    run = PROJECT.invoke(
        Path(artifact_dir),
        {
            "requests": [
                {"kind": "report", "context": context, "receipts": receipts},
                {"kind": "plan", "context": context, "receipts": receipts},
            ]
        },
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "evidence_through_week": record.get("through_week"),
        "intake_log": context["intake_log"][-12:],
        "visits_on_the_receipts": [_receipt_summary(entry) for entry in receipts],
        "units_spent": desk.units_spent(receipts),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "depot": context["depot"]},
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
            "depot": context["depot"],
            "month": context["month"],
            "units_spent": desk.units_spent(receipts),
        },
        "public": {
            "session": session,
            "board_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_visit(
    artifact_dir: Path, week: Any, job_class: Any, jobs: Any, receipt_id: Any
) -> Mapping[str, Any]:
    return desk.collect(
        Path(artifact_dir), workload.current(), week, job_class, jobs, receipt_id
    )
