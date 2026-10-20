'Agent-visible tools for SWE-stream-multiplexing.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("link/session.py", "link/streams.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="ground station workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the link files, the settings every drill runs a "
                "link with, and the drills under project_records/. replay runs "
                "one drill against the current workspace on a throwaway copy "
                "and returns what this station did at every step of it: the "
                "frames it put on the radio, what the depot unit made of them, "
                "and whatever else that drill was recorded to look at."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a drill under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
