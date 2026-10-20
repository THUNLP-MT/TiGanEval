'Agent-visible tools for Research-weighted-coverage-shift.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="dispatch board reporting workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the depot, the month, the board's terms, the "
                "audit terms and night roster, the monthly traffic report, how "
                "many audit units are spent and left, every visit on the "
                "receipts and the working records on file. replay runs the "
                "notebook the way one recorded session's author ran it, on the "
                "evidence as it stood that week, and prints that session's "
                "notes and intake log beside whatever the notebook returned. "
                "collect books one night visit: the crew times the jobs with a "
                "stopwatch and hands the durations back, the receipt is "
                "appended to visit_receipts.json and the units are spent; a "
                "request the desk turns away still costs a unit, and repeating "
                "a receipt_id returns the receipt already on file unbilled."
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
                    "week": {
                        "type": "integer",
                        "description": "Audit week to put the crew out on.",
                    },
                    "job_class": {
                        "type": "string",
                        "description": "Job class the night is booked on.",
                    },
                    "jobs": {
                        "type": "integer",
                        "description": "How many jobs of that class to time.",
                    },
                    "receipt_id": {
                        "type": "string",
                        "description": "A short label you choose for this night.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
