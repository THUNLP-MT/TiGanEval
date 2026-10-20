'`run_project` for the EM-9 soak campaign: status, day replay, chamber block.'

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
        content += _block("Campaign", outcome["measurements"])
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
        outcome = harness.run_block(
            workspace,
            arguments.get("drive_a"),
            arguments.get("case_temp_c"),
            arguments.get("ports"),
            arguments.get("chamber_days"),
            arguments.get("lot"),
            arguments.get("block_id"),
        )
        receipt = dict(outcome["receipt"])
        if not outcome["ran"]:
            content = (
                f"Block {receipt['block_id']} was already on the receipts; "
                "nothing was charged."
            )
        elif receipt["refusal"]:
            content = (
                f"The desk handed block {receipt['block_id']} back on "
                f"{receipt['served_on']}: {receipt['refusal']}. The days were charged."
            )
        else:
            content = (
                f"Block {receipt['block_id']} ran {receipt['modules_returned']} spares of "
                f"{receipt['lot']} at {receipt['drive_a']} A and {receipt['case_temp_c']} C "
                f"for {receipt['chamber_days_asked']} days from {receipt['served_on']}, "
                f"and came back with {receipt['rows_returned']} bench rows."
            )
        content += _block("Receipt", receipt)
        content += _block(
            "Budget",
            {
                "days_spent": outcome["days_spent"],
                "days_left": outcome["days_left"],
                "spares_left": outcome["spares_left"],
            },
        )
        data = {key: value for key, value in outcome.items()}
        return TaskToolResult(content=content, data={"action": "collect", **data})

    raise ValueError("run_project.action must be status, replay or collect")
