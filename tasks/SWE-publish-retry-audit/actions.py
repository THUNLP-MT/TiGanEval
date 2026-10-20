'Agent-visible tools for SWE-publish-retry-audit.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("publish/uploader.py", "publish/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="release publishing workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the publishing files, the release settings, and the "
                "releases under project_records/ with the artifacts and publishers "
                "each one involves. replay runs one recorded release against the "
                "current workspace on copied state and returns what everyone can "
                "see: every call the host received, what each target ended up "
                "holding next to what the build made, the summary the release job "
                "printed, and the pause before each further try."
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
