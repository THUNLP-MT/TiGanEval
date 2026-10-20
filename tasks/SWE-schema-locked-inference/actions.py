'Agent-visible tools for SWE-schema-locked-inference.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("pipeline/pipeline.py", "pipeline/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="tabular pipeline workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "Inspect or rehearse the deterministic training and serving pipeline. "
                "status reports the run directory contract and lists the recorded "
                "rehearsals. replay runs one recorded rehearsal against a copy of the "
                "current workspace and returns the raw timeline: each operation, its "
                "result or error, the design matrices the model received, and the "
                "artifacts each run left behind. Neither action delivers anything for "
                "review."
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
