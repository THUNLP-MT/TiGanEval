'Agent-visible tools for Research-sequential-rollout-stopping.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="one-tap reorder watch workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the watch, the charter's terms, the share-day "
                "points spent and left, every booking on the ledger and the "
                "working sessions on record. replay runs the notebook the way "
                "one recorded working session ran it, on the evidence as it "
                "stood that day, and prints that session's notes and daily numbers beside whatever the "
                "notebook returned. collect books the watch forward for a "
                "number of days at a treated share, returns those days' "
                "enrolment rows, the reorders published on them by arm and the "
                "topic's counters, appends the receipt to "
                "collection_ledger.json and spends the share-day points; "
                "repeating a call_id returns the receipt already on the ledger "
                "unbilled."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay", "collect"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a working session under project_records/.",
                    },
                    "share_pct": {
                        "type": "integer",
                        "description": "Treated share of new enrolments to serve, in percent.",
                    },
                    "days": {"type": "integer", "description": "How many more days to serve."},
                    "hold_ramp": {
                        "type": "boolean",
                        "description": (
                            "true holds the share for the whole booking; false lets the "
                            "charter's weekly step raise it."
                        ),
                    },
                    "call_id": {
                        "type": "string",
                        "description": "A short label you choose for this booking.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
