'Agent-visible tools for SWE-recovery-construct-effects.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("pricing/recovery.py", "pricing/triage.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="rating run workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the pricing files, the rulebook limits and the nights "
                "under project_records/ with the orders and rules each one covers. "
                "replay prices one recorded night against the current workspace on "
                "copied state and returns the night's telemetry: what each order "
                "ended as with the attempts and steps it used, every row the ledger "
                "holds, every incident raised with its label, and the rating "
                "reservations opened and given back."
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
