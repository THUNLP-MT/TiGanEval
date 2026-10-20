'Agent-visible tools for SWE-module-resolution-cache.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("runtime/loader.py", "runtime/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="scripting runtime workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the runtime files, the deployment's store tree and link "
                "table, and the stretches under project_records/ with the runs and jobs "
                "each one drives. replay runs one stretch against the current workspace "
                "on copied state and returns what the console and the store recorded: "
                "every job with its declarations, its own log and how it ended, every "
                "use with the file it reached, everything the store was asked for and "
                "opened, the licence checks, the catalog the run ended with, the "
                "loader's own report, and whatever the process wrote to its console."
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
