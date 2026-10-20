'Agent-visible tools for SWE-streaming-json-reader.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("client/reader.py", "client/support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="collector client workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status lists the recorded response traces and the collector's "
                "read-ahead slack. replay re-runs one recorded trace against the "
                "current workspace and reports, for every response in it, what the "
                "gateway sent and what this build did with it: the records it "
                "handed over, what it raised, the body bytes pulled as each record "
                "reached the caller, and the transport's chunk, byte, and close "
                "counters."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a project record.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
