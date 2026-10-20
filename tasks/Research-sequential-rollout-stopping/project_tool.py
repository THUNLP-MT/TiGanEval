'`run_project` for the one-tap reorder watch: status, session replay, booking.'

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
        content += _block("Watch", outcome["measurements"])
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
        content += _block("Working session", outcome["measurements"])
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
            arguments.get("share_pct"),
            arguments.get("days"),
            arguments.get("hold_ramp"),
            arguments.get("call_id"),
        )
        receipt = dict(outcome["receipt"])
        content = (
            f"Booking {receipt['call_id']} served {receipt['share_pct']} percent for "
            f"{receipt['days']} days from {receipt['served_from']}."
            if outcome["ran"]
            else f"Booking {receipt['call_id']} was already on the ledger; nothing was billed."
        )
        content += _block("Receipt", receipt)
        if outcome["ran"]:
            content += _block("Enrolment on the new days", outcome["enrolment"])
            content += _block("Reorders published on the new days", outcome["reorders"])
            content += _block("Ingestion on the new days", outcome["ingestion"])
        content += _block(
            "Budget",
            {"points_spent": outcome["points_spent"], "points_left": outcome["points_left"]},
        )
        data = {key: value for key, value in outcome.items()}
        return TaskToolResult(content=content, data={"action": "collect", **data})

    raise ValueError("run_project.action must be status, replay or collect")
