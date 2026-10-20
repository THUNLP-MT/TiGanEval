'Agent-visible tools for SWE-exclusive-consumer-lease.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("dispatch/assignment.py", "dispatch/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="fleet job scheduler workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status reports the fleet's classes, their windows and the recorded "
                "shifts available. replay runs one recorded shift against the "
                "scheduler in the tree and returns what happened: every operation "
                "the supervisor performed, which worker ran each job, the notices "
                "each worker received, what each worker was holding at its busiest, "
                "and the operator console at the end. A replay changes nothing and "
                "delivers nothing."
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
