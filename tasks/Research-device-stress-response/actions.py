'Agent-visible tools for Research-device-stress-response.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="QR-40 burst qualification workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the lot, the plan's terms, the chamber hours "
                "spent and left, what the stores hold, every session on the "
                "receipts and the working days on record. replay runs the "
                "notebook the way one recorded working day ran it, on the "
                "evidence as it stood then, and prints that day's notes, bench "
                "sheet and ladder beside whatever the notebook returned. "
                "collect puts one sheet in front of the chamber desk: it "
                "returns that session's per-unit readings and results and the "
                "bench's block readings for it, appends the receipt to "
                "session_receipts.json and charges the hour; a sheet the desk "
                "will not take comes back with the reason and the hour is "
                "charged all the same; repeating a booking_id returns the "
                "receipt already on the stream unbilled."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay", "collect"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a day under project_records/.",
                    },
                    "bench": {"type": "string", "description": "Which bench to run the session on."},
                    "batch": {
                        "type": "string",
                        "description": "Which coupling batch in stores to draw the units from.",
                    },
                    "cartridge": {
                        "type": "string",
                        "description": "Which pressure cartridge to run them at.",
                    },
                    "dwell_min": {
                        "type": "integer",
                        "description": "How many minutes to hold each coupling at pressure.",
                    },
                    "units": {"type": "integer", "description": "How many couplings to put on."},
                    "booking_id": {
                        "type": "string",
                        "description": "A short label you choose for this session.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
