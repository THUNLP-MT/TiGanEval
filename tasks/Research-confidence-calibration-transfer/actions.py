'Agent-visible tools for Research-confidence-calibration-transfer.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="listing review readout workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the queue, its window, the cut and the bar in "
                "force, the sheet's bands, the audit terms, the traffic report, "
                "the credits charged and left, and every batch on the receipts. "
                "replay runs the notebook the way one recorded working session "
                "ran it, on the log as it stood that day, and prints that "
                "session's notes beside whatever the notebook returned. collect "
                "books one batch with the adjudication desk: it names a cell "
                "(one channel and one intake plan), works "
                "that cell's backlog out of band, returns those listings with "
                "an outcome written against them, appends the receipt to "
                "audit_receipts.json and charges the credits; repeating a "
                "batch_id returns the receipt already on file uncharged."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay", "collect"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a record under project_records/.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Intake channel the cell is on.",
                        "enum": ["web", "mobile", "partner_feed", "reseller_import"],
                    },
                    "period": {
                        "type": "string",
                        "description": "The intake plan the cell is on, as the log writes it.",
                    },
                    "listings": {
                        "type": "integer",
                        "description": "How many listings to have adjudicated out of band.",
                    },
                    "batch_id": {
                        "type": "string",
                        "description": "A short label you choose for this batch.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
