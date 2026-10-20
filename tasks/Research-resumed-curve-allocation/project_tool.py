'`run_project` for the allocation note: status, record replay, one booking.'

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
        content += _block("Window", outcome["measurements"])
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
        outcome = harness.run_booking(
            workspace,
            arguments.get("config_id"),
            arguments.get("node_type"),
            arguments.get("hours"),
            arguments.get("receipt_id"),
        )
        receipt = dict(outcome["receipt"])
        head = {key: value for key, value in receipt.items() if key != "observed"}
        observed = receipt.get("observed", {})
        rows = list(observed.get("rows", ()))
        if not outcome["ran"]:
            content = (
                f"Job {receipt['receipt_id']} was already on the receipt stream; "
                "nothing was billed."
            )
        elif receipt.get("refusal"):
            content = (
                f"The console would not run job {receipt['receipt_id']}: "
                f"{receipt['refusal']}."
            )
        else:
            content = (
                f"Job {receipt['receipt_id']} ran {receipt['steps_returned']} steps of "
                f"{receipt['config_id']} on {receipt['node_type']} and wrote "
                f"{len(rows)} rows."
            )
        content += _block("Receipt", head)
        if observed.get("segment_id"):
            content += _block(
                "Where it went on the ledger",
                {
                    "segment_id": observed.get("segment_id"),
                    "resumed_from": observed.get("resumed_from"),
                },
            )
        content += _block("Rows written", rows[:6])
        if len(rows) > 6:
            content += (
                f"\n\n{len(rows) - 6} further rows are on the receipt in "
                "collection_receipts.json."
            )
        content += _block(
            "Grant",
            {
                "hours_charged": outcome["hours_charged"],
                "hours_left": outcome["hours_left"],
            },
        )
        return TaskToolResult(
            content=content,
            data={
                "action": "collect",
                "receipt": head,
                "rows_written": len(rows),
                "hours_charged": outcome["hours_charged"],
                "hours_left": outcome["hours_left"],
                "ran": outcome["ran"],
            },
        )

    raise ValueError("run_project.action must be status, replay or collect")
