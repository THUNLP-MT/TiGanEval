'`run_project` for the plate screen review: status, record replay, one rig day.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _harness() -> Any:
    from .private import harness

    return harness


def _record_path(workspace: Path, arguments: Mapping[str, Any]) -> Path:
    raw = arguments.get("record")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("run_project replay requires a record path")
    path = (workspace / raw).resolve()
    if workspace not in path.parents or path.suffix != ".json" or not path.is_file():
        raise ValueError("record must name an existing JSON file inside the workspace")
    return path


def _block(title: str, value: Any) -> str:
    return f"\n\n{title}:\n" + json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))
    harness = _harness()

    if action == "status":
        outcome = harness.public_status(workspace)
        content = str(outcome["summary"])
        content += _block("Bench", outcome["measurements"])
        content += _block("Working days on record", outcome["records"])
        content += _block("Source files", outcome["sources"])
        return TaskToolResult(
            content=content,
            data={
                "action": "status",
                "measurements": dict(outcome["measurements"]),
                "records": list(outcome["records"]),
                "sources": dict(outcome["sources"]),
            },
        )

    if action == "replay":
        path = _record_path(workspace, arguments)
        include_inputs = arguments.get("include_inputs", False)
        if not isinstance(include_inputs, bool):
            raise ValueError("run_project replay include_inputs must be a boolean")
        outcome = harness.public_replay(workspace, path, include_inputs=include_inputs)
        content = str(outcome["summary"])
        content += _block("Record", outcome["measurements"])
        content += _block("That working day", outcome["public"]["working_day"])
        content += _block(
            "What your notebook returned for that working day",
            {
                "report": outcome["public"].get("report_returned"),
                "next_collection": outcome["public"].get("next_collection_returned"),
                "console_error": outcome["public"].get("console_error"),
                "diagnostic": outcome["public"].get("diagnostic"),
                "printed": outcome["public"].get("stdout"),
            },
        )
        if outcome["public"].get("bench_today"):
            content += _block(
                "The bench as it stands now, and what your notebook returns for it",
                outcome["public"]["bench_today"],
            )
        if include_inputs:
            content += _block("Exact inputs used for each replay", outcome["public"]["inputs"])
        else:
            content += (
                "\n\nFor the exact context and receipts used for each replay, call replay "
                "with this record and include_inputs=true. Source files describe the "
                "current workspace; the working day's snapshot may be earlier."
            )
        return TaskToolResult(
            content=content,
            data={
                "action": "replay",
                "record": path.relative_to(workspace).as_posix(),
                "measurements": dict(outcome["measurements"]),
                "public": dict(outcome["public"]),
            },
        )

    if action == "collect":
        outcome = harness.run_booking(
            workspace, arguments.get("day"), arguments.get("booking_id")
        )
        receipt = dict(outcome["receipt"])
        if outcome["ran"]:
            content = (
                f"Rig day {receipt['day_id']} ran under booking {receipt['receipt_id']}."
                if not receipt.get("refusal")
                else (
                    f"The desk handed back the sheet for {receipt['day_id']} under booking "
                    f"{receipt['receipt_id']} and charged the day."
                )
            )
        else:
            content = (
                f"Booking {receipt['receipt_id']} already ran as rig day "
                f"{receipt['day_id']}; nothing new went on the rig."
            )
        content += _block("Receipt", receipt)
        content += _block(
            "Booking sheet",
            {
                "rig_days_charged": outcome["rig_days_spent"],
                "rig_days_left": outcome["rig_days_left"],
            },
        )
        return TaskToolResult(content=content, data={"action": "collect", **dict(outcome)})

    raise ValueError("run_project.action must be status, replay or collect")
