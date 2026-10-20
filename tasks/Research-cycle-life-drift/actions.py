'Agent-visible tools for Research-cycle-life-drift.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="cell cycle-life study workspace",


            max_chars=120_000,
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the bench as it stands: the rack and its setpoints, the "
                "firmware the tester is on, the booking balance, the records, and every "
                "session this campaign has paid for. replay opens one record under "
                "project_records/, prints the tester's own export for it and what your "
                "analysis.py returns for the study as it stands. collect puts a booking "
                "on the tester now -- a bay, a protocol, a number of cells and a request "
                "id you choose -- and appends the session's receipt to "
                "session_receipts.json; it spends channel hours and cannot be undone. "
                "Repeating a request id returns the session it already ran."
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
                    "bay": {"type": "string", "description": "For collect: a bay on the rack."},
                    "protocol": {
                        "type": "string",
                        "enum": ["standard", "stepped"],
                        "description": "For collect: the charge protocol the cells run under.",
                    },
                    "cells": {"type": "integer", "description": "For collect: how many cells."},
                    "request_id": {
                        "type": "string",
                        "description": "For collect: your own name for this booking.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
