'Agent-visible tools for SWE-pii-lineage-checker.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("lineage/tracer.py", "lineage/summaries.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="lineage checker workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the lineage files, the audit's field, mask and export "
                "tables and the drills under project_records/. replay runs one drill "
                "against the current workspace on a throwaway copy and returns what "
                "this checker did at every scan of it: the scan label and module count, "
                "the report this build produced, and the companion measurements that "
                "drill was recorded to show."
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
