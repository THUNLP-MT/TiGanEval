'Agent-visible tools for SWE-log-viewport-follow.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("console/rich_pane.py", "console/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="incident console workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the console files, the settings in console.toml and "
                "the recorded sessions under project_records/ with the pane "
                "settings each one ran with. replay drives one recorded session "
                "against the current workspace on a copied tree and returns the "
                "console view: for every event the pane's scroll position, badge, "
                "drawn line count and widest line, which entry is at the top of "
                "the viewport, the rows on screen, and anything the pane posted "
                "to the session audit, next to what was written down that night."
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
