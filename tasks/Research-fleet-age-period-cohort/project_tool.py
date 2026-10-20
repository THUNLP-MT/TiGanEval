'`run_project` for the fleet note: status, record replay, inspection day.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _views() -> Any:
    from .private import tools

    return tools


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
        content += _block("Region", outcome["measurements"])
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
        outcome = views.run_day(
            workspace,
            arguments.get("depot"),
            arguments.get("builds"),
            arguments.get("age_band"),
            arguments.get("vans"),
            arguments.get("day"),
            arguments.get("receipt_id"),
        )
        receipt = dict(outcome["receipt"])
        head = {key: value for key, value in receipt.items() if key != "observed"}
        rows = list(receipt.get("observed", {}).get("rows", ()))
        if not outcome["ran"]:
            content = (
                f"Day {receipt['receipt_id']} is already on the receipts; nothing was charged."
            )
        elif receipt.get("refusal"):
            content = (
                f"Day {receipt['receipt_id']} came back from the depot unworked: "
                f"{receipt['refusal']}. The day is charged."
            )
        else:
            content = (
                f"Day {receipt['receipt_id']} at {receipt['depot']} returned "
                f"{receipt['vans_returned']} vans and {receipt['faults_returned']} faults "
                f"under the {receipt['walkaround_ref']} card."
            )
        content += _block("Receipt", head)
        content += _block("Vans walked round", rows[:5])
        if len(rows) > 5:
            content += (
                f"\n\n{len(rows) - 5} further vans are on the receipt in audit_receipts.json."
            )
        content += _block(
            "Days",
            {"days_charged": outcome["days_charged"], "days_left": outcome["days_left"]},
        )
        return TaskToolResult(
            content=content,
            data={
                "action": "collect",
                "receipt": head,
                "vans_returned": receipt["vans_returned"],
                "faults_returned": receipt["faults_returned"],
                "days_charged": outcome["days_charged"],
                "days_left": outcome["days_left"],
                "ran": outcome["ran"],
            },
        )

    raise ValueError("run_project.action must be status, replay or collect")
