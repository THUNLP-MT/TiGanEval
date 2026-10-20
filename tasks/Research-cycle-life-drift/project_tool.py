'`run_project` for the cycle-life study: the bench, one record, one booking.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _private() -> tuple[Any, Any, Any]:
    from .private import harness, lab, workload

    return harness, lab, workload


def _record(workspace: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = arguments.get("record")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("run_project replay needs the path of a record")
    path = (workspace / raw).resolve()
    if workspace not in path.parents or path.suffix != ".json" or not path.is_file():
        raise ValueError("record must name an existing JSON file inside the workspace")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("a record must contain a JSON object")
    return value


def _block(title: str, value: Any) -> str:
    return f"\n\n{title}:\n" + json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _export_block(export: Mapping[str, Any] | None) -> str:
    "The session's capacity checks as the bench console lists them."

    if not export:
        return "\n\nWhat the tester wrote:\n  this record is not a session of its own"
    head = (
        f"session {export['session_id']}, firmware {export['firmware']}, "
        f"reference cell {export['reference_cell_ah']} Ah, "
        f"chamber trace {export['chamber_logged_c']} C, "
        f"{export['cycles_run']} cycles, {export['channel_hours']} channel hours"
    )
    lines = [
        "  {} on channel {}: {}".format(
            cell["cell_id"],
            cell["channel"],
            " ".join(f"{cycle}={amp_hours}" for cycle, amp_hours in cell["checkpoints"]),
        )
        for cell in export["cells"]
    ]
    return "\n\nWhat the tester wrote:\n  " + head + "\n" + "\n".join(lines)


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))
    harness, lab, workload = _private()

    if action == "status":
        outcome = harness.public_status(workspace)
        content = str(outcome["summary"])
        content += _block("Bench", outcome["measurements"])
        content += _block("Records", outcome["records"])
        content += _block("Sessions the campaign has paid for", outcome["sessions_paid_for"])
        return TaskToolResult(content=content, data={"action": "status", **dict(outcome)})

    if action == "replay":
        record = _record(workspace, arguments)
        outcome = harness.run_public_replay(workspace, record)
        content = str(outcome["summary"])
        content += _block("Record", outcome["measurements"])
        content += _export_block(outcome["public"]["instrument_export"])
        content += _block("The operator's sheet", outcome["public"]["record"])
        content += _block("Sessions the campaign has paid for",
                          outcome["public"]["sessions_paid_for"])
        content += _block("What your notebook returned", outcome["public"]["notebook"])
        return TaskToolResult(
            content=content,
            data={"action": "replay", "record": str(arguments.get("record")),
                  "measurements": dict(outcome["measurements"]),
                  "public": dict(outcome["public"])},
        )

    if action == "collect":
        outcome = lab.collect(
            workspace,
            workload.CURRENT_LOT,
            arguments.get("bay"),
            arguments.get("protocol"),
            arguments.get("cells"),
            arguments.get("request_id"),
        )
        receipt = dict(outcome["receipt"])
        summary = (
            f"Session {receipt['session_id']} ran on the tester and its receipt is in "
            f"{lab.RECEIPT_FILE}."
            if outcome["executed"]
            else f"Request {receipt['request_id']} already ran as session "
                 f"{receipt['session_id']}; nothing new was put on the tester."
        )
        content = summary
        content += _block("Receipt", receipt)
        content += _block("Booking", {
            "executed": outcome["executed"],
            "channel_hours_remaining": outcome["channel_hours_remaining"],
        })
        return TaskToolResult(content=content, data={"action": "collect", **dict(outcome)})

    raise ValueError("run_project.action must be status, replay or collect")
