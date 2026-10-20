'Agent-visible tools for SWE-stencil-boundary-modes.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("tilekit/sweep.py", "tilekit/edges.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="tile rendering workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the package files, the boundary vocabulary, the "
                "kernel library and the recorded nights under project_records/. "
                "replay runs one recorded night against the current workspace on "
                "a throwaway copy and returns what this build did at every pass "
                "in it: the job config, the tile, the coverage map, and whatever "
                "else that night was kept for."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a night under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
