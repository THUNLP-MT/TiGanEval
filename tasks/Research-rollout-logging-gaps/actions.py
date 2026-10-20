'Agent-visible tools for Research-rollout-logging-gaps.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="checkout hint readout workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the readout, the archive terms, the rescan units "
                "spent and left, every rescan on the receipt stream and the "
                "sessions on record. replay runs the notebook the way one recorded "
                "session's operator ran it, on the evidence as it stood that day, "
                "and prints that session's notes and daily numbers beside whatever "
                "the notebook returned. collect buys one archive rescan for a day "
                "and an arm, returns the crawler count it finds, appends the "
                "receipt to audit_receipts.json and spends a unit; repeating a "
                "scan_id returns the receipt already on the stream unbilled."
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
                    "day": {"type": "string", "description": "Day to rescan, as YYYY-MM-DD."},
                    "arm": {"type": "string", "enum": ["control", "treatment"]},
                    "scan_id": {
                        "type": "string",
                        "description": "A short label you choose for this rescan.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
