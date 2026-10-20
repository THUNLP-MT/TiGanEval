'What `run_project` shows: the campaign as it stands, one working day, one block.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import chamber, workload
from . import world as w


def read_record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    "The campaign's evidence as it stood at the end of one working day."

    through = str(record["through_day"])
    context = world.context()
    context["traces"] = [
        row for row in context["traces"] if str(row["logged_at"])[:10] <= through
    ]
    return context


def export_view(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The export laid out module by module, as the reporting job lays it out.'

    rows: dict[str, dict[str, Any]] = {}
    for row in context["traces"]:
        name = str(row["module_id"])
        entry = rows.setdefault(
            name,
            {
                "module_id": name,
                "lot": row["lot"],
                "rack": row["rack"],
                "drive_a": row["drive_a"],
                "rows": 0,
                "first_logged_at": row["logged_at"],
                "last_logged_at": row["logged_at"],
                "first_elapsed_h": row["elapsed_h"],
                "last_elapsed_h": row["elapsed_h"],
                "first_output_mw": row["output_mw"],
                "last_output_mw": row["output_mw"],
            },
        )
        entry["rows"] += 1
        if str(row["logged_at"]) < str(entry["first_logged_at"]):
            entry["first_logged_at"] = row["logged_at"]
            entry["first_elapsed_h"] = row["elapsed_h"]
            entry["first_output_mw"] = row["output_mw"]
        if str(row["logged_at"]) > str(entry["last_logged_at"]):
            entry["last_logged_at"] = row["logged_at"]
            entry["last_elapsed_h"] = row["elapsed_h"]
            entry["last_output_mw"] = row["output_mw"]
    return [rows[name] for name in sorted(rows)]


def status(artifact_dir: Path, live_receipts) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    stream, error = live_receipts(root)
    world = workload.CURRENT
    context = world.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = read_record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("date", "operator", "record_id", "through_day")},
        })
    return {
        "summary": (
            f"The {context['campaign']} soak campaign, the plan's terms and the "
            "working days on record."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "family": context["family"],
            "build_month": context["build_month"],
            "field_drive_a": context["field_drive_a"],
            "hold_temp_c": context["hold_temp_c"],
            "target_loss": context["target_loss"],
            "meter_full_scale_mw": context["meter_full_scale_mw"],
            "meter_read_spread_mw": context["meter_read_spread_mw"],
            "reference_source_mw": context["reference_source_mw"],
            "reference_module_id": context["reference_module_id"],
            "racks": context["racks"],
            "catalogue": context["catalogue"],
            "budget": context["budget"],
            "spares": context["spares"],
            "spares_incoming_mw": context["spares_incoming_mw"],
            "spares_left": world.spares_left(stream),
            "rig_out_of_service": context["rig_out_of_service"],
            "chamber_days_spent": world.days_spent(stream),
            "chamber_days_left": world.days_left(stream),
            "next_day_the_schedule_holds": world.served_on(stream),
            "blocks_on_the_receipts": [
                {
                    "block_id": item["block_id"],
                    "drive_a": item["drive_a"],
                    "case_temp_c": item["case_temp_c"],
                    "ports_asked": item["ports_asked"],
                    "chamber_days_asked": item["chamber_days_asked"],
                    "lot": item["lot"],
                    "modules_returned": item["modules_returned"],
                    "rows_returned": item["rows_returned"],
                    "days_charged": item["days_charged"],
                    "served_on": item["served_on"],
                    "refusal": item["refusal"],
                }
                for item in stream
            ],
            "receipt_stream": error or "reads back in order",
            "editable_files": ["analysis.py", "support.py"],
        },
        "records": records,
    }


def replay(artifact_dir: Path, record_path: Path, project, live_receipts) -> Mapping[str, Any]:
    'Run the notebook the way that recorded working day ran it.'

    record = read_record(record_path)
    world = workload.CURRENT
    context = snapshot(world, record)
    stream, _error = live_receipts(Path(artifact_dir))
    receipts = [
        item for item in stream if str(item["served_on"]) <= str(record.get("date", ""))
    ]
    run = project.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "receipts": receipts},
            {"kind": "plan", "context": context, "receipts": receipts},
        ]},
    )
    day = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through_day": record.get("through_day"),
        "module_index": [dict(item) for item in context["modules"]],
        "export_by_module": export_view(context),
        "blocks_on_the_receipts": [
            {"block_id": item["block_id"], "drive_a": item["drive_a"],
             "case_temp_c": item["case_temp_c"], "ports_asked": item["ports_asked"],
             "rows_returned": item["rows_returned"], "days_charged": item["days_charged"],
             "refusal": item["refusal"]}
            for item in receipts
        ],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} working day could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "campaign": context["campaign"]},
            "public": {"day": day, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} working day ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "evidence_through_day": record.get("through_day"),
            "field_drive_a": context["field_drive_a"],
            "hold_temp_c": context["hold_temp_c"],
            "meter_full_scale_mw": context["meter_full_scale_mw"],
            "rows_in_the_export": len(context["traces"]),
        },
        "public": {
            "day": day,
            "report_returned": results[0] if results else None,
            "next_block_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_block(
    artifact_dir: Path,
    live_receipts,
    drive_a: Any,
    case_temp_c: Any,
    ports: Any,
    chamber_days: Any,
    lot: Any,
    block_id: Any,
) -> Mapping[str, Any]:
    stream, error = live_receipts(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return chamber.collect(
        Path(artifact_dir), workload.CURRENT, drive_a, case_temp_c, ports, chamber_days,
        lot, block_id,
    )
