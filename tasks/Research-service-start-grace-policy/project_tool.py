'`run_project` for the Northfield desk: status, session replay, booking.'

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
        content += _block("Sessions on record", outcome["records"])
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
        outcome = harness.run_booking(
            workspace,
            arguments.get("segment"),
            arguments.get("hold_share"),
            arguments.get("slots"),
            arguments.get("receipt_id"),
            arguments.get("week"),
        )
        receipt = dict(outcome["receipt"])
        if not outcome["ran"] and receipt.get("refusal"):
            content = (
                f"The desk handed week {receipt['receipt_id']} back: {receipt['refusal']}."
            )
        elif outcome["ran"]:
            content = (
                f"Week {receipt['receipt_id']} served {receipt['segment']} at "
                f"{int(round(float(receipt['hold_share']) * 100))} percent held for "
                f"{receipt['slots_asked']} slots."
            )
        else:
            content = (
                f"Week {receipt['receipt_id']} was already on the receipts; "
                "nothing was charged."
            )
        content += _block("Receipt", receipt)
        if outcome.get("flags"):
            content += _block("Flags the week returned", outcome["flags"])
        content += _block(
            "Grant",
            {"slots_charged": outcome["slots_spent"], "slots_left": outcome["slots_left"]},
        )
        data = {key: value for key, value in outcome.items()}
        return TaskToolResult(content=content, data={"action": "collect", **data})

    raise ValueError("run_project.action must be status, replay or collect")
