'`run_project` for the bundle board pack: status, record replay, capture request.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _harness() -> Any:
    from .private import publish

    return publish


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
        content += _block("Campaign", outcome["measurements"])
        content += _block("Records on file", outcome["records"])
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
        content += _block("Session", outcome["measurements"])
        content += _block("What the session shows", outcome["public"])
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
        outcome = harness.run_capture(
            workspace,
            arguments.get("duty_profile"),
            arguments.get("firmware"),
            arguments.get("condition"),
            arguments.get("rows"),
            arguments.get("receipt_id"),
        )
        receipt = dict(outcome["receipt"])
        head = {key: value for key, value in receipt.items() if key != "observed"}
        rows = list(receipt.get("observed", {}).get("rows", ()))
        if not outcome["ran"] and receipt.get("refusal"):
            content = (
                f"Capture request {receipt['receipt_id']} was turned away: "
                f"{receipt['refusal']}."
            )
        elif outcome["ran"]:
            content = (
                f"Capture request {receipt['receipt_id']} came back with "
                f"{receipt['rows_returned']} annotated captures."
            )
        else:
            content = (
                f"Capture request {receipt['receipt_id']} was already on file; "
                "nothing was billed."
            )
        content += _block("Receipt", head)
        content += _block("Rows returned", rows[:3])
        if len(rows) > 3:
            content += (
                f"\n\n{len(rows) - 3} further rows are on the receipt in "
                "capture_receipts.json."
            )
        content += _block(
            "Credits",
            {
                "credits_spent": outcome["credits_spent"],
                "credits_left": outcome["credits_left"],
            },
        )
        return TaskToolResult(
            content=content,
            data={
                "action": "collect",
                "receipt": head,
                "rows_returned": receipt["rows_returned"],
                "credits_spent": outcome["credits_spent"],
                "credits_left": outcome["credits_left"],
                "ran": outcome["ran"],
            },
        )

    raise ValueError("run_project.action must be status, replay or collect")
