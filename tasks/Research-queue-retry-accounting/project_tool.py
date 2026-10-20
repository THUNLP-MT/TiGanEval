'`run_project` for the quote route failure review: status, session replay, trace pull.'

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
        content += _block("Review", outcome["measurements"])
        content += _block("Working sessions on record", outcome["records"])
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
        outcome = harness.run_trace(
            workspace, arguments.get("minute"), arguments.get("pool"),
            arguments.get("trace_id"),
        )
        receipt = dict(outcome["receipt"])
        content = (
            f"Trace {receipt['trace_id']} covers {receipt['minute']} on {receipt['pool']}."
            if outcome["ran"]
            else f"Trace {receipt['trace_id']} was already on the ledger; nothing was billed."
        )
        content += _block("Receipt", receipt)
        content += _block("Edge rows for that pool-minute", outcome["rows"])
        content += _block(
            "Budget",
            {"units_spent": outcome["units_spent"], "units_left": outcome["units_left"]},
        )
        return TaskToolResult(content=content, data={"action": "collect", **outcome})

    raise ValueError("run_project.action must be status, replay or collect")
