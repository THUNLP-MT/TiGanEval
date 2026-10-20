'Agent-visible tools for SWE-conditional-validation.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("orders/policy.py", "orders/contract.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="order platform workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the modules, the entity documents and the records "
                "under project_records/. replay runs one record against the current "
                "workspace on a throwaway copy and returns what this build did at "
                "every step of it: the payloads the write path took or turned away, "
                "the patch and condition it handed the store, what the store did "
                "with them, what the read path returned, and what the published "
                "contract said."
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
