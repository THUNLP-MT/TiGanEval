'Agent-visible tools for SWE-config-drift-baselines.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("estate/reconcile.py", "estate/notes.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="estate compliance workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the compliance service's files and the recorded "
                "console runs under project_records/ with the environments each "
                "one touches. replay drives one recorded run against the current "
                "workspace on copied state and returns the console's listings: "
                "every operation, each night's numbers next to the numbers the "
                "old script wrote, the durable record ledger, and the detected "
                "rows in the operator queue."
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
