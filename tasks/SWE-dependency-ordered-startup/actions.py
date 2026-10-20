'Agent-visible tools for SWE-dependency-ordered-startup.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("bootstrap/startup.py", "bootstrap/planner.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="API service start-up workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the bootstrap files and the recorded start-ups under "
                "project_records/ with the services and deploy settings each one "
                "involves. replay brings one recorded manifest up against the "
                "current workspace and returns the boot ledger: what the console "
                "drove, every connect step and handle, every resolve, and the "
                "measurements from the run."
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
