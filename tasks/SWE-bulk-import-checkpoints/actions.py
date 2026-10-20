'Agent-visible tools for SWE-bulk-import-checkpoints.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("loader/importer.py", "loader/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="catalogue loader workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status reports the recorded nights available and the load envelope "
                "the warehouse team publishes. replay runs one recorded night against "
                "the current workspace on copied state and returns what each run did: "
                "the report it returned, its transactions, its rows, and the catalogue "
                "it left behind. A replay changes nothing and delivers nothing."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a project record.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
