'Agent-visible tools for Research-planning-forecast-booking.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="dispatch desk planning workspace",


            max_chars=60_000,
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign's shift calendar, the carrier terms, the "
                "allowance left, every order the desk has been charged for and the "
                "working days on record. replay opens one record under project_records/, "
                "prints the sheets and the ledger as they stood that day and what your "
                "analysis.py returns for them. collect puts an order on the road: hand it "
                "a shift, a list of {area, window, vans} lines and an order id you choose. "
                "The carrier runs the shift, the meter writes a receipt into "
                "ledger/receipts.jsonl and the van-hours come off the allowance. An order "
                "the carrier hands back comes with a reason and the desk fee is charged "
                "all the same. Repeating an order id returns the order it already ran."
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
                    "shift": {
                        "type": "string",
                        "description": "For collect: the shift the order is for.",
                    },
                    "order": {
                        "type": "array",
                        "description": "For collect: the order, one line per area and window.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "area": {"type": "string"},
                                "window": {"type": "string"},
                                "vans": {"type": "integer"},
                            },
                            "required": ["area", "window", "vans"],
                            "additionalProperties": False,
                        },
                    },
                    "order_id": {
                        "type": "string",
                        "description": "For collect: your own short name for this order.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
