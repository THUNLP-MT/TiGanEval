'Agent-visible tools for SWE-ddl-format-stability.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("ddl/formatter.py", "ddl/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="migration formatter workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the migration files in this checkout, the project "
                "records, and the directory's line_width and indent. replay formats "
                "the migration files one record names with the formatter currently "
                "in the tree and returns what came out, unjudged: the source, the "
                "formatted text, the statement rows the formatter reported, the "
                "width of every written line, and the text the same formatter "
                "wrote when that output went back in. It compares nothing for you."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a project record to replay.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
