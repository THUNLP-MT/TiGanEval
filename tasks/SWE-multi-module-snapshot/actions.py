'Agent-visible tools for SWE-multi-module-snapshot.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("plugins/coordinator.py", "plugins/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="plugin sandbox workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the sandbox files and the recorded runs under "
                "project_records/ with the plugins each one loads. replay runs one "
                "recorded run against the current workspace on copied state and "
                "returns the console log: every step the console drove, what each "
                "dump held when it was read, and the sandbox after each step."
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
