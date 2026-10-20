'Agent-visible tools for Research-staggered-region-rollout.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="Halcombe batching rollout workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the rollout, the wave board's terms, the "
                "region-weeks charged and left, every receipt on the ledger and "
                "the working sessions on record. replay runs the notebook the "
                "way one recorded session ran it, on the evidence as it stood "
                "that day, and prints that session's notes, the metros it "
                "walked day by day and whatever the notebook returned. collect "
                "books one metro for one week with a share of its orders held "
                "back, returns both arms' daily rows, appends the receipt to "
                "wave_receipts.json and charges the region-week; the board hands "
                "a week back rather than serving it when its own terms do not "
                "allow it, and charges for that too. Asking for a region-week "
                "already on the receipts returns that receipt uncharged."
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
                    "region": {
                        "type": "string",
                        "description": "The metro to book, as it is spelled on the register.",
                    },
                    "week": {
                        "type": "string",
                        "description": "The Monday of the week to book, as the board lists it.",
                    },
                    "holdback_share": {
                        "type": "integer",
                        "description": (
                            "Percentage of that metro's orders to keep off batching "
                            "for the week."
                        ),
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
