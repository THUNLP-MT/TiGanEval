'Agent-visible tools for SWE-durability-acknowledgement.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("engine/durability.py", "engine/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="storage engine workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the engine files and the sessions recorded under "
                "project_records/. replay runs one recorded session against the "
                "current workspace and returns the node console's row for every "
                "step: the log's offsets, what recovery would return, the number "
                "this write path reports next to the same number computed from "
                "the log, the durability events delivered, every parked client "
                "and how it was settled, and the sequence numbers released so far."
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
