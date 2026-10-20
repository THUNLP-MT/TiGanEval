'Agent-visible tools for SWE-session-bundle-replay.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("bundle/recorder.py", "bundle/replay.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="notebook console workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the console package, the files under samples/ and the "
                "recorded sessions under project_records/. replay drives one recorded "
                "session against the current workspace on copied state and returns the "
                "console log: every operation, what each cell put on screen, what the "
                "recorder reported, and what each bundle file holds afterwards."
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
