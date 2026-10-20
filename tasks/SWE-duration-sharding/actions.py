'Agent-visible tools for SWE-duration-sharding.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("sharding/planner.py", "sharding/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="CI shard planner workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the planner files, the operations note and the runs "
                "under project_records/. replay runs one recorded CI run against "
                "the current workspace on a throwaway tree and returns what every "
                "machine did: the walk order it was handed, the generation the "
                "history file was at, the files it planned, the plan the runner "
                "read back with the price it put on each file beside what that "
                "generation of the history holds for it, the history document "
                "after each write, and each shard's predicted and realised "
                "minutes beside the same run under the split CI has always had."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a run under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
