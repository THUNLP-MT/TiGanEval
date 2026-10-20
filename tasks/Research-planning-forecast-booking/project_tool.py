'`run_project` for the dispatch desk: status, record replay, one booked shift.'

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
        content += _block("Desk", outcome["measurements"])
        content += _block("Working days on record", outcome["records"])
        return TaskToolResult(
            content=content,
            data={
                "action": "status",
                "measurements": dict(outcome["measurements"]),
                "records": list(outcome["records"]),
            },
        )

    if action == "replay":
        path = _record_path(workspace, arguments)
        outcome = harness.public_replay(workspace, path)
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
        if outcome["public"].get("desk_today"):
            content += _block(
                "The desk as it stands now, and what your notebook returns for it",
                outcome["public"]["desk_today"],
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
            workspace,
            arguments.get("shift"),
            arguments.get("order"),
            arguments.get("order_id"),
        )
        receipt = dict(outcome["receipt"])
        if outcome["ran"]:
            content = (
                f"Shift {receipt['shift_id']} ran under order {receipt['order_id']}."
                if not receipt.get("refusal")
                else (
                    f"The carrier handed back order {receipt['order_id']} for "
                    f"{receipt['shift_id']} and charged the desk fee."
                )
            )
        else:
            content = (
                f"Order {receipt['order_id']} already ran as shift "
                f"{receipt['shift_id']}; nothing new went on the road."
            )
        content += _block("Receipt", receipt)
        content += _block(
            "Allowance",
            {
                "shifts_settled": outcome["shifts_settled"],
                "allowance_left": outcome["allowance_left"],
            },
        )
        return TaskToolResult(content=content, data={"action": "collect", **dict(outcome)})

    raise ValueError("run_project.action must be status, replay or collect")
