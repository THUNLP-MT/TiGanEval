'Agent-visible tools for SWE-incremental-scan-cache.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("scanner/engine.py", "scanner/exchange.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="CI security-scan workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the recorded rehearsals and the cache envelope the "
                "build volume publishes for a run. replay runs one recorded "
                "rehearsal against a copy of the current workspace and returns its "
                "raw telemetry: each run's analysed files, separate summaries of "
                "its report and a full re-analysis of the same tree, its cache "
                "summary, and the cache left on the volume beside that run's limits."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a project record to replay.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
