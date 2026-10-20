'Agent-visible tools for Research-invitation-spillover-design.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("report.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="gate-pass campaign reporting workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign, the month's window, the target, the "
                "credits granted, spent and left, the mail house terms, every drum "
                "on the floor with its price, its names left and its allowance, "
                "every booking on the ledger and the working records on file. "
                "replay runs the notebook the way one recorded session's author "
                "ran it, on the evidence as it stood that day, and prints that "
                "session's notes, its counter rows and the register's own stamps "
                "beside whatever the notebook returned."
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


        experiment_tool(timeout=90.0),
        *control_tools(),
    )
