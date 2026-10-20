'Agent-visible tools for SWE-message-expiry-routing.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("broker/channel.py", "broker/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="notification broker workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the broker files and the drills under "
                "project_records/ with the queues each one declares. replay runs "
                "one drill against the current workspace on copied state and "
                "returns the operator's notes from that drill next to every "
                "operation this broker performed: queue contents, deadlines, what "
                "each get handed out, and the settlement ledger."
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
