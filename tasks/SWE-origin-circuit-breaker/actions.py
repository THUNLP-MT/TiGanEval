'Agent-visible tools for SWE-origin-circuit-breaker.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("gateway/breaker.py", "gateway/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="edge gateway workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the gateway files and the stretches of traffic under "
                "project_records/ with the clients and origins each one involves. "
                "replay runs one stretch against the current workspace on copied "
                "state and returns the access log: every operation and what the "
                "call it drove ended as, every attempt that left the process, and "
                "what each origin received."
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
