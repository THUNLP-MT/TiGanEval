'run_project for the summary relay: status and replay, telemetry only.'

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
    path = (workspace / raw).resolve()
    if workspace not in path.parents or path.suffix != ".json" or not path.is_file():
        raise ValueError("record must name an existing JSON file inside the workspace")
    return path


def _rendered(outcome: Mapping[str, Any], action: str) -> TaskToolResult:
    summary = str(outcome.get("summary", "The project tool ran."))
    measurements = dict(outcome.get("measurements", {}) or {})
    observed = dict(outcome.get("observed", {}) or {})
    content = summary
    if measurements:
        content += "\n\nMeasurements:\n" + json.dumps(
            measurements, indent=2, ensure_ascii=False, sort_keys=True
        )
    if observed:
        content += "\n\nWhat the relay did:\n" + json.dumps(
            observed, indent=2, ensure_ascii=False, sort_keys=True
        )
    return TaskToolResult(
        content=content,
        data={"action": action, "measurements": measurements, "observed": observed},
    )


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))
    harness = _private_harness()
    if action == "status":
        outcome = harness.public_status(workspace)
    elif action == "replay":
        outcome = harness.run_public_rehearsal(workspace, _record_path(workspace, arguments))
    else:
        raise ValueError("run_project.action must be status or replay")
    if not isinstance(outcome, Mapping):
        raise TypeError("the summary relay project tool must return a mapping")
    return _rendered(outcome, action)
