'Agent-visible tools for SWE-alias-name-mapping.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("intake/mapper.py", "intake/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="partner intake workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the intake files and the recorded runs of partner "
                "posts under project_records/ with the shape and partners each one "
                "involves. replay runs one of them against the current workspace on "
                "copied state and returns the intake log: every operation, the keys "
                "the partner sent, which key each field's value came out of, and "
                "what intake built or bounced. It returns no verdict."
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
