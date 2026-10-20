'Agent-visible tools for SWE-persisted-query-restore.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("handset/persister.py", "handset/adapters.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="Kerbside handset workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the handset files and the recorded sessions under "
                "project_records/ with the queries each one has on the device. "
                "replay runs one session against the current workspace on copied "
                "state and returns the console log: what was written onto the "
                "device, every operation the console drove and the screen it "
                "left, the load and depot counts at each step, and the depot's "
                "own log."
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
