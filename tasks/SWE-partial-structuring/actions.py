'Agent-visible tools for SWE-partial-structuring.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("ingest/recover.py", "ingest/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="provider ingest workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the recorded drops and the columns the provider "
                "contract declares. replay runs one recorded drop against the "
                "current workspace on copied state and returns what happened "
                "payload by payload: what the reading came back with, what the "
                "ledger row holds, and what the ticket says. A replay changes "
                "nothing and publishes nothing."
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
