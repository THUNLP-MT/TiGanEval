'Agent-visible tools for SWE-state-scoped-data.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("fulfilment/scopes.py", "fulfilment/helpers.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="workflow engine workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status reports the recorded scenarios available and the chart the "
                "engine runs: every state, what it declares, and where a held order "
                "comes back in. replay runs one recorded scenario against the current "
                "workspace and returns what the engine reported for each event: the "
                "states the order is in, its data, the audit lines, and the handler "
                "steps the engine would not serve. A replay changes nothing and "
                "delivers nothing."
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
