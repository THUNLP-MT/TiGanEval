'Agent-visible tools for SWE-evaluation-profiling.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("policy/engine.py", "policy/profile.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="decision service workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the policy files, the work-unit budget one decision "
                "may spend, and the drills under project_records/. replay runs one "
                "drill against the current workspace on a throwaway copy and "
                "returns what this service did at every step of it: the decision "
                "for each request and whatever that drill looks at, from work "
                "units to the report rows this build produced."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a drill under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
