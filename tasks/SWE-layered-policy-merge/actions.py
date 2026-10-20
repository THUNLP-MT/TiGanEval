'Agent-visible tools for SWE-layered-policy-merge.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("edge/compile.py", "edge/pin.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="ingress control-plane workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the edge files, the routes and their pods, the "
                "policy documents committed under config/policies/, and the "
                "drills under project_records/. replay runs one drill against "
                "the current workspace on a throwaway copy and returns what "
                "this control plane and proxy did at every step of it: the "
                "plan each push produced, whether the proxy took it, the "
                "cookie lines, and where each request landed."
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
