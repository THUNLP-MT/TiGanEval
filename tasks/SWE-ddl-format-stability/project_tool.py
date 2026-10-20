'run_project for the migration formatter: status and replay, telemetry only.'

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


def _rendered(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))
    harness = _harness()

    if action == "status":
        status = dict(harness.public_status(workspace))
        return TaskToolResult(
            content=(
                "migration files in this checkout: "
                + ", ".join(status["migration_files"])
                + "\nproject records: "
                + ", ".join(status["project_records"])
                + f"\nline_width: {status['line_width']}  indent: {status['indent']}"
            ),
            data={"action": "status", **status},
        )
    if action == "replay":
        outcome = dict(harness.run_public_replay(workspace, _record_path(workspace, arguments)))
        if outcome.get("execution_error"):
            content = (
                f"replayed {outcome['record_id']}\n"
                f"the formatter stopped before writing a file: {outcome['execution_error']}\n"
                f"{outcome.get('diagnostic', '')}"
            )
        else:
            content = (
                f"replayed {outcome['record_id']} over "
                f"{len(outcome['files'])} migration file(s); "
                f"line_width {outcome['line_width']}, indent {outcome['indent']}\n\n"
                + _rendered(outcome["files"])
            )
            if outcome.get("same_schema"):
                content += "\n\nfiles recorded as describing the same schema:\n" + _rendered(
                    outcome["same_schema"]
                )
        return TaskToolResult(content=content, data={"action": "replay", **outcome})
    raise ValueError("run_project.action must be status or replay")
