'Agent-visible tools for Research-threshold-eligibility-effect.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="standing-score offer campaign workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign, the council's terms, the review "
                "files charged and left, every lot on the receipts and the "
                "working sessions on record. replay runs the notebook the way "
                "one recorded session ran it, on the evidence as it stood that "
                "day, and prints that session's notes, the rows by standing "
                "score around the line and by run week, and whatever the "
                "notebook returned. collect asks the file desk for a lot of "
                "files from one run week inside a band either side of the "
                "line, returns those files with the score the run used, the "
                "credits filed against them and their orders to today, appends "
                "the receipt to review_receipts.json and charges the grant; "
                "the desk refuses some lots and charges for them, and "
                "repeating a receipt_id returns the receipt already on file "
                "uncharged."
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
                    "week": {
                        "type": "integer",
                        "description": "Which weekly scoring run to pull files from.",
                    },
                    "band": {
                        "type": "number",
                        "description": "How many points either side of the line the desk pulls from.",
                    },
                    "above_share": {
                        "type": "number",
                        "description": "Share of the lot pulled from above the line.",
                    },
                    "files": {"type": "integer", "description": "How many files to review."},
                    "receipt_id": {
                        "type": "string",
                        "description": "A short label you choose for this lot.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
