'run_project for SWE-incremental-scan-cache: status and replay, telemetry only.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


def _private_harness() -> Any:
    from .private import harness

    return harness


def _record_path(workspace: Path, arguments: Mapping[str, Any]) -> Path:
    raw = arguments.get("record")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("run_project replay requires a record path")
    root = workspace.resolve()
    path = (root / raw).resolve()
    if root not in path.parents or path.suffix != ".json" or not path.is_file():
        raise ValueError("record must name an existing JSON file inside the workspace")
    return path


def _rendered(outcome: Mapping[str, Any], action: str) -> TaskToolResult:
    summary = str(outcome.get("summary", "The project tool ran."))
    measurements = outcome.get("measurements", {})
    measurements = dict(measurements) if isinstance(measurements, Mapping) else {}
    public = outcome.get("public", {})
    public = dict(public) if isinstance(public, Mapping) else {}

    content = summary
    if measurements:
        content += "\n\nPublished limits and this rehearsal's tree:\n" + json.dumps(
            measurements, indent=2, ensure_ascii=False, sort_keys=True
        )
    for name, value in sorted(public.items()):
        if isinstance(value, list) and all(isinstance(row, Mapping) for row in value):
            rows = "\n".join(
                json.dumps(dict(row), ensure_ascii=False, sort_keys=True) for row in value
            )
            content += f"\n\n{name} ({len(value)}):\n{rows or '(none)'}"
        else:
            content += f"\n\n{name}:\n" + json.dumps(
                value, indent=2, ensure_ascii=False, sort_keys=True
            )
    return TaskToolResult(
        content=content,
        data={"action": action, "measurements": measurements, "public": public},
    )


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    action = str(arguments.get("action", "status"))
    workspace = Path(context.workspace).resolve()
    harness = _private_harness()

    if action == "status":
        outcome = harness.public_status(workspace)
    elif action == "replay":
        outcome = harness.run_public_rehearsal(workspace, _record_path(workspace, arguments))
    else:
        raise ValueError("run_project.action must be status or replay")

    if not isinstance(outcome, Mapping):
        raise TypeError("the scan-cache project harness must return a mapping")
    return _rendered(outcome, action)
