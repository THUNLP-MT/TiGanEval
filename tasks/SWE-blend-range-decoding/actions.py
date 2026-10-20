'Agent-visible tools for SWE-blend-range-decoding.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("plate/bands.py", "plate/compose.py", "plate/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="catalogue compositor workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the compositor files and, for every recorded "
                "scenario, the shots it runs and what each of their layers "
                "stores. replay runs one scenario against the current workspace "
                "on a throwaway copy and returns what this build did at every "
                "step of it: the plate it published for each shot, the plate the "
                "design tool publishes for that shot, and, where the scenario "
                "writes the source files back, the grips that went in beside the "
                "grips that came out."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a scenario under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
