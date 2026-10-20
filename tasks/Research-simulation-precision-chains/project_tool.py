'`run_project` for the capacity precision study: status, session replay, jobs.'

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
        content += _block("Study", outcome["measurements"])
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
        outcome = harness.run_job(
            workspace,
            arguments.get("chain_id"),
            arguments.get("start_new"),
            arguments.get("steps"),
            arguments.get("call_id"),
        )
        receipt = dict(outcome["receipt"])
        if not outcome["ran"]:
            content = f"Job {receipt['call_id']} was already on the ledger; nothing was billed."
        elif receipt["refusal"]:
            content = (
                f"The console refused job {receipt['call_id']}: {receipt['refusal']}. "
                f"It charged {receipt['steps_charged']} steps."
            )
        else:
            content = (
                f"Job {receipt['call_id']} returned {receipt['steps_returned']} steps on "
                f"{receipt['chain_id']}."
            )
        content += _block("Receipt", receipt)
        rows = list(outcome.get("rows", ()))
        stored: dict[str, Any] | None = None
        if rows:
            stored = {
                "chain_id": outcome["chain_id"],
                "path": f"chains/{outcome['chain_id']}.csv",
                "columns": outcome["columns"],
                "rows_returned": len(rows),
            }
            content += _block(
                "Stored output",
                stored,
            )
        content += _block(
            "Grant",
            {"steps_charged": outcome["steps_charged_total"], "steps_left": outcome["steps_left"]},
        )
        public = {
            "action": "collect",
            **{key: value for key, value in dict(outcome).items() if key != "rows"},
        }
        if stored is not None:
            public.update({"path": stored["path"], "rows_returned": stored["rows_returned"]})
        return TaskToolResult(content=content, data=public)

    raise ValueError("run_project.action must be status, replay or collect")
