'Agent-visible tools for SWE-grouped-test-barriers.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("harness/sequencing.py", "harness/rendezvous.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="device lab night runner workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the runner's files, the lab inventory by bench, and "
                "the recorded nights under project_records/ with the handsets, "
                "benches and cases each one uses. replay runs one recorded night "
                "against the current workspace on copied state and returns the "
                "console log: every step every handset took with its lab-time "
                "reading, every arrival at a named point and every resume from "
                "one, the morning report's rows, the handset pool's checkouts and "
                "returns, and anything still unfinished when nobody could take "
                "another turn."
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
