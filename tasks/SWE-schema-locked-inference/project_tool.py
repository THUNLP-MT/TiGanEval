'run_project for SWE-schema-locked-inference: status and replay, telemetry only.'

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


def _rendered(outcome: Mapping[str, Any]) -> TaskToolResult:
    'Render one telemetry payload; the reader draws the conclusions.'

    summary = str(outcome.get("summary", ""))
    measurements = outcome.get("measurements", {})
    measurements = dict(measurements) if isinstance(measurements, Mapping) else {}
    observed = outcome.get("observed", {})
    observed = dict(observed) if isinstance(observed, Mapping) else {}

    content = summary
    if measurements:
        content += "\n\n" + json.dumps(
            measurements, indent=2, ensure_ascii=False, sort_keys=True
        )
    if observed:
        content += "\n\n" + json.dumps(
            observed, indent=2, ensure_ascii=False, sort_keys=True
        )
    return TaskToolResult(
        content=content,
        data={"measurements": measurements, "observed": observed},
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
        raise TypeError("the tabular pipeline harness must return a mapping")
    return _rendered({**outcome, "measurements": {"action": action, **dict(outcome.get("measurements", {}))}})
