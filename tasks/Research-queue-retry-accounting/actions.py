'Agent-visible tools for Research-queue-retry-accounting.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="quote route failure review workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the review, the archive terms, the pools, the "
                "fleets, the daily dashboard, the trace units spent and left, "
                "every unit on the receipt ledger and the working sessions on "
                "record. replay runs the notebook the way one recorded "
                "session's operator ran it, on the export as it stood that day, "
                "and prints that session's notes, its dashboard and the last "
                "evening minute by minute beside whatever the notebook "
                "returned. collect pulls one pool-minute out of the edge "
                "archive, returns that pool's rows for that minute grouped by "
                "source and outcome, appends the receipt to trace_receipts.json "
                "and spends a unit; repeating a trace_id returns the receipt "
                "already on the ledger unbilled."
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
                    "minute": {
                        "type": "string",
                        "description": "Minute to pull, as YYYY-MM-DDTHH:MM.",
                    },
                    "pool": {
                        "type": "string",
                        "description": "Edge pool to pull that minute from.",
                    },
                    "trace_id": {
                        "type": "string",
                        "description": "A short label you choose for this pull.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
