'Agent-visible tools for SWE-encrypted-backup-pipeline.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("nightly/pipeline.py", "nightly/restore.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="nightly archive workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the job's files and the stretches of nights under "
                "project_records/ with the nights and the window each one involves. "
                "replay runs one stretch against the current workspace on copied "
                "state and returns what the console saw: the row each night "
                "returned, every event each destination saw, what each destination "
                "holds afterwards, and what the drill got back for each object."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a record under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
