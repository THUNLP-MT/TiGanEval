'Agent-visible tools for Research-calibration-drift-bench.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="bushing qualification workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign, the two rigs, the booking terms, the "
                "bench-hours spent and left, every session on the receipt stream and "
                "the working sessions on record. replay runs the notebook the way one "
                "recorded working session's operator ran it, on the evidence as it "
                "stood that day, and prints that session's notes and table beside "
                "whatever the notebook returned. collect runs one session on the bench "
                "now: name a rig and either a part from stores or the reference block, "
                "and it returns the reading, appends the receipt to bench_receipts.json "
                "and charges the hours. Repeating a run_id returns the receipt already "
                "on the stream without charging again."
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
                    "rig": {"type": "integer", "enum": [1, 2]},
                    "part": {
                        "type": "string",
                        "description": "A part in stores, such as A-3330-09.",
                    },
                    "reference_block": {
                        "type": "boolean",
                        "description": "Run the certified block instead of a part.",
                    },
                    "cycles": {
                        "type": "integer",
                        "description": "Cycles for a part session; the bench runs the qualification block.",
                    },
                    "run_id": {
                        "type": "string",
                        "description": "A short label you choose for this session.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
