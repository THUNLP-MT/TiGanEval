'Agent-visible tools for Research-source-apportionment-tracer.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="Block A header apportionment workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the window, the agreement's terms, the slots "
                "spent and left, every visit on the ledger and the working "
                "sessions on record. replay runs the notebook the way one "
                "recorded session ran it, on the evidence as it stood that "
                "day, and prints that session's notes and that day's rows "
                "beside whatever the notebook returned. collect sends the "
                "contractor out once: it draws that many slots at one point "
                "with the channels and dwell you name, returns the desk's "
                "receipt with the readings, appends it to sample_ledger.json "
                "and spends the slots; repeating a call_id returns the receipt "
                "already on the ledger unbilled."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay", "collect"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a session under project_records/.",
                    },
                    "point": {
                        "type": "string",
                        "description": "Where the contractor is to draw the slots.",
                    },
                    "channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Which of the analyser's channels to read: conductivity, "
                            "marker, ripple. The ripple channel needs the hire module."
                        ),
                    },
                    "dwell_min": {
                        "type": "integer",
                        "description": "Minutes per slot: five or thirty.",
                    },
                    "samples": {
                        "type": "integer",
                        "description": "How many slots to draw on this visit.",
                    },
                    "call_id": {
                        "type": "string",
                        "description": "A short label you choose for this visit.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
