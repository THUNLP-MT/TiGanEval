'`run_project` for the dispatch board: status, record replay, night visit.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _desk() -> Any:
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
    desk = _desk()

    if action == "status":
        outcome = desk.public_status(workspace)
        content = str(outcome["summary"])
        content += _block("Depot", outcome["measurements"])
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
        outcome = desk.public_replay(workspace, path)
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
        outcome = desk.run_visit(
            workspace,
            arguments.get("week"),
            arguments.get("job_class"),
            arguments.get("jobs"),
            arguments.get("receipt_id"),
        )
        receipt = dict(outcome["receipt"])
        head = {key: value for key, value in receipt.items() if key != "observed"}
        rows = list(receipt.get("observed", {}).get("rows", ()))
        if outcome["ran"]:
            content = (
                f"Night visit {receipt['receipt_id']} timed {receipt['jobs_returned']} "
                f"{receipt['job_class']} jobs in week {receipt['week']}."
            )
        elif receipt.get("refusal"):
            content = (
                f"Night visit {receipt['receipt_id']} was turned away: "
                f"{receipt['refusal']}."
            )
        else:
            content = (
                f"Night visit {receipt['receipt_id']} was already on the receipts; "
                "nothing was billed."
            )
        content += _block("Receipt", head)
        content += _block("Jobs timed", rows[:4])
        if len(rows) > 4:
            content += (
                f"\n\n{len(rows) - 4} further jobs are on the receipt in "
                "visit_receipts.json."
            )
        content += _block(
            "Units",
            {"units_spent": outcome["units_spent"], "units_left": outcome["units_left"]},
        )
        return TaskToolResult(
            content=content,
            data={
                "action": "collect",
                "receipt": head,
                "jobs_returned": receipt["jobs_returned"],
                "units_spent": outcome["units_spent"],
                "units_left": outcome["units_left"],
                "ran": outcome["ran"],
            },
        )

    raise ValueError("run_project.action must be status, replay or collect")
