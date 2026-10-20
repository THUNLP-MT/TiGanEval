'Agent-visible tools for SWE-request-coalescing.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("relay/dispatcher.py", "relay/sharing.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="summary relay workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status reports the recorded windows and the desks the relay serves. "
                "replay runs one recorded window against the current workspace on a "
                "copy and returns what happened: every caller and what it was "
                "answered with, every rendering the backend ran, the usage ledger, "
                "and the counters the relay reported. A replay changes nothing and "
                "answers nobody."
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
