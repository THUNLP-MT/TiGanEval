'Agent-visible tools for SWE-keyset-pagination.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("listing/pages.py", "listing/shelves.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="catalogue listing workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the listing files, the settings in service.toml and "
                "the recorded scenarios under project_records/ with the catalogue "
                "and page sizes each one uses. replay runs one scenario against the "
                "current workspace on a copied catalogue and returns the request "
                "log: every request and what came back, every edit merchandising "
                "made between requests, and every product id delivered in request "
                "order."
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
