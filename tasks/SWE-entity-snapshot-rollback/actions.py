'Agent-visible tools for SWE-entity-snapshot-rollback.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("scene/checkpoint.py", "scene/tools.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="level editor workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the editor files, the declared trait and relation "
                "keys, and the recorded sessions under project_records/. replay "
                "runs one session against the current workspace on copied state "
                "and returns every step it performed: the level after each step "
                "with each prop's id, slot and generation, the status bar digest, "
                "the digest of every checkpoint file saved so far, whatever a "
                "revert raised, and what the change panel printed."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a session under project_records/.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
