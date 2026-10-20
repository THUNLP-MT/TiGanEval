'Agent-visible tools for SWE-concurrent-map-merge.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("board/merge.py", "board/helpers.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="whiteboard client workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the sessions support kept and what the workspace holds. "
                "replay runs one recorded session against the current workspace on "
                "copied state and returns its support note and what every copy did: "
                "the operations people "
                "made, the packets each copy was given, the state vector and board "
                "digest after each packet, what the sync service resent on reconnect, "
                "and the board, vector and merge account each copy ended with. A "
                "replay changes nothing and delivers nothing."
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
