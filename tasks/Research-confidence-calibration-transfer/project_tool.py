'`run_project` for the auto-clear readout: status, record replay, one batch.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _views() -> Any:
    from .private import views

    return views


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
    views = _views()

    if action == "status":
        outcome = views.public_status(workspace)
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
        outcome = views.public_replay(workspace, path)
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
        outcome = views.run_batch(
            workspace,
            arguments.get("channel"),
            arguments.get("period"),
            arguments.get("listings"),
            arguments.get("batch_id"),
        )
        receipt = dict(outcome["receipt"])
        head = {key: value for key, value in receipt.items() if key != "observed"}
        rows = list(receipt.get("observed", {}).get("rows", ()))
        if not outcome["ran"]:
            content = (
                f"Batch {receipt['batch_id']} was already on the receipts; nothing was charged."
            )
        elif receipt.get("refusal"):
            content = (
                f"The desk turned batch {receipt['batch_id']} away: {receipt['refusal']}."
            )
        else:
            content = (
                f"Batch {receipt['batch_id']} came back with {receipt['listings_returned']} "
                f"adjudicated listings from the {receipt['channel']} cell."
            )
        content += _block("Receipt", head)
        content += _block("Listings returned", rows[:5])
        if len(rows) > 5:
            content += (
                f"\n\n{len(rows) - 5} further listings are on the receipt in "
                "audit_receipts.json."
            )
        content += _block(
            "Credits",
            {
                "credits_charged": outcome["credits_charged"],
                "credits_left": outcome["credits_left"],
            },
        )
        return TaskToolResult(
            content=content,
            data={
                "action": "collect",
                "receipt": head,
                "listings_returned": receipt["listings_returned"],
                "credits_charged": outcome["credits_charged"],
                "credits_left": outcome["credits_left"],
                "ran": outcome["ran"],
            },
        )

    raise ValueError("run_project.action must be status, replay or collect")
