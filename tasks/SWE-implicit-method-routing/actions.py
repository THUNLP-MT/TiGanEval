'Agent-visible tools for SWE-implicit-method-routing.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("surface/routing.py", "surface/metering.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="delivery portal workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the portal files and the stretches of partner traffic "
                "under project_records/ with the surface each one assembles. replay "
                "runs one stretch against the current workspace on copied state and "
                "returns the request log: the operations the surface ended up "
                "serving, what the portal publishes about them, what every request "
                "got back with its work units, and the capacity report."
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
