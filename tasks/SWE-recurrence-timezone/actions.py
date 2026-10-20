'Agent-visible tools for SWE-recurrence-timezone.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("recur/schedule.py", "recur/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="reminder schedule workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the engine files, the zone table and the scenes "
                "under project_records/. replay runs one scene against the "
                "current workspace and returns what support or the operator "
                "wrote down for it next to every step this engine performed: "
                "the reminders it would send with their wall-clock rendering "
                "and offset, what it wrote out and what the importer read back, "
                "each feed next to the merge, and each slice the dispatcher "
                "would walk."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a scene under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
