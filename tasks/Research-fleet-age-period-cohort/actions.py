'Agent-visible tools for Research-fleet-age-period-cohort.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="fleet engineering reporting workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the region, the window of returns, the depots and "
                "the cards they raise faults under, the lease terms, the audit's "
                "terms, the review's terms, how many days are charged and left, "
                "every day on the receipts and the working records on file. "
                "replay runs the notebook the way one recorded session's author "
                "ran it, on the evidence as it stood that month, and prints that "
                "session's notes beside whatever the notebook returned. collect "
                "books one inspection day: it sends the inspector to a depot for "
                "a group of build years inside an age band, returns the vans he "
                "walked round with the faults each raised under that depot's own "
                "card, appends the receipt to audit_receipts.json and charges the "
                "day. A booking the audit plan does not allow comes back refused "
                "with the day still charged; repeating a receipt_id returns the "
                "receipt already on file unbilled."
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
                    "depot": {"type": "string", "description": "Depot the day is worked at."},
                    "builds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Build groups to walk round, such as [\"2021-H2\", \"2022-H1\"].",
                    },
                    "age_band": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Lowest and highest months of age to include, lowest first.",
                    },
                    "vans": {"type": "integer", "description": "How many vans to walk round."},
                    "day": {
                        "type": "string",
                        "description": "Calendar day the inspector works, as YYYY-MM-DD.",
                    },
                    "receipt_id": {
                        "type": "string",
                        "description": "A short label you choose for this day.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
