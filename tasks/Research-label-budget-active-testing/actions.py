'Agent-visible tools for Research-label-budget-active-testing.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="ticket triage review workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the desk, the vendor's terms and dates, the credits "
                "spent and left, the sessions on the ledger and the working "
                "sessions on file. replay runs the notebook the way one recorded "
                "working session ran it, on the ledger as it stood that day, and "
                "prints that session's notes beside whatever the notebook "
                "returned. collect places one labelling session with the vendor: "
                "it charges the set-up and the prices, appends the receipts to "
                "label_ledger.jsonl and returns them; repeating a session_id "
                "returns the session already on the ledger unbilled."
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
                    "session_id": {
                        "type": "string",
                        "description": "A short label you choose for this labelling session.",
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Pool item ids, in the order the reviewer is to work them.",
                    },
                    "draw": {
                        "type": "object",
                        "description": (
                            "Instead of items: {rule, n} with rule one of uncertainty, "
                            "confidence, pool_order, plus optional channel, segment, "
                            "product_line or priority filters."
                        ),
                        "properties": {
                            "rule": {"type": "string",
                                     "enum": ["uncertainty", "confidence", "pool_order"]},
                            "n": {"type": "integer"},
                            "channel": {"type": "string"},
                            "segment": {"type": "string"},
                            "product_line": {"type": "string"},
                            "priority": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
