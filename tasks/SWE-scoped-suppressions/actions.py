'Agent-visible tools for SWE-scoped-suppressions.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("audit/waivers.py", "audit/shared.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="estate policy audit workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the audit files, the rule table and the profiles, "
                "every policy document with each entry's path and line span and "
                "what the rule table objects to in it, and the review sessions "
                "under project_records/. replay runs one session against the "
                "current workspace on copied files and returns, for every "
                "document it read, what the rule table objects to, what the "
                "report came back with, the three counters, and the numbers the "
                "last review signed off."
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
