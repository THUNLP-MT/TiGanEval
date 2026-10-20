'Agent-visible tools for Research-screening-followup-design.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="plate screen review workspace",


            max_chars=120_000,
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the current budget, booking summaries and source-file "
                "directory. replay opens one record under project_records/, prints its "
                "operator notes, input-source references and what your analysis.py returns. "
                "Set include_inputs=true on replay to also return the exact context and "
                "receipts used for the historical and, when present, current replay. collect "
                "books the next rig day: hand it a sheet of {part, runs} entries and a "
                "booking id you choose. The rig runs the sheet, writes a receipt into "
                "bench_receipts.json and takes the day off the sheet. A sheet the desk "
                "will not take comes back with a reason and the day is charged all the "
                "same. Repeating a booking id returns the day it already ran."
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
                    "include_inputs": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "For replay: also return each replay's complete context and "
                            "receipts. Defaults to operator notes, source references and results."
                        ),
                    },
                    "day": {
                        "type": "array",
                        "description": "For collect: the day sheet, one entry per part.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "part": {
                                    "type": "string",
                                    "description": "A plate id, the reference plate or the incumbent part.",
                                },
                                "runs": {"type": "integer"},
                            },
                            "required": ["part", "runs"],
                            "additionalProperties": False,
                        },
                    },
                    "booking_id": {
                        "type": "string",
                        "description": "For collect: your own short name for this rig day.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
