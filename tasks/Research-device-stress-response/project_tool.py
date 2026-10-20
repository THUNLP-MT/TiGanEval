'`run_project` for the QR-40 qualification: status, day replay, chamber session.'

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
        content += _block("Lot", outcome["measurements"])
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
        content += _block("Working day", outcome["measurements"])
        content += _block("What the day shows", outcome["public"])
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
        outcome = harness.run_session(
            workspace,
            arguments.get("bench"),
            arguments.get("batch"),
            arguments.get("cartridge"),
            arguments.get("dwell_min"),
            arguments.get("units"),
            arguments.get("booking_id"),
        )
        receipt = dict(outcome["receipt"])
        if not outcome["ran"]:
            content = (
                f"Session {receipt['booking_id']} was already on the receipts; "
                "nothing was charged."
            )
        elif receipt["refusal"]:
            content = (
                f"The desk handed session {receipt['booking_id']} back on "
                f"{receipt['served_on']}: {receipt['refusal']}. The hour was charged."
            )
        else:
            content = (
                f"Session {receipt['booking_id']} ran {receipt['units_returned']} couplings of "
                f"{receipt['batch']} at {receipt['cartridge']} on {receipt['bench']} for "
                f"{receipt['dwell_min']} minutes, on {receipt['served_on']}."
            )
        content += _block("Receipt", receipt)
        content += _block(
            "Budget",
            {
                "hours_spent": outcome["hours_spent"],
                "hours_left": outcome["hours_left"],
                "stores_left": outcome["stores_left"],
            },
        )
        data = {key: value for key, value in outcome.items()}
        return TaskToolResult(content=content, data={"action": "collect", **data})

    raise ValueError("run_project.action must be status, replay or collect")
