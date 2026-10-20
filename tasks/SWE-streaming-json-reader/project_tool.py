'run_project for SWE-streaming-json-reader: status and replay, telemetry only.'

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


def _rendered(responses: Any) -> str:
    'One compact JSON object per response, one per line.'

    return "\n".join(
        json.dumps(entry, ensure_ascii=False, separators=(",", ":")) for entry in responses
    )


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))
    harness = _harness()

    if action == "status":
        status = dict(harness.public_status(workspace))
        listed = ", ".join(status["project_records"])
        return TaskToolResult(
            content=(
                f"recorded traces: {listed}\n"
                f"read-ahead slack the collector allows: "
                f"{status['read_ahead_slack_bytes']} bytes\n"
                f"workspace content hash: {status['artifact_hash']}"
            ),
            data={"action": "status", **status},
        )

    if action == "replay":
        path = _record_path(workspace, arguments)
        outcome = dict(harness.run_public_record(workspace, path))
        relative = path.relative_to(workspace).as_posix()
        if "execution_error" in outcome:
            return TaskToolResult(
                content=(
                    f"replayed {relative}\n{outcome['scene']}\n\n"
                    f"nothing was read: {outcome['execution_error']}"
                ),
                data={"action": "replay", "record": relative, **outcome},
            )
        content = (
            f"replayed {relative}\n{outcome['scene']}\n"
            f"read-ahead slack the collector allows: "
            f"{outcome['read_ahead_slack_bytes']} bytes\n\n"
            "For each response: what the gateway sent, and what this build did "
            "with it.\n" + _rendered(outcome["responses"])
        )
        return TaskToolResult(
            content=content,
            data={"action": "replay", "record": relative, **outcome},
        )

    raise ValueError("run_project.action must be status or replay")
