'Agent-visible tools for Research-device-mixture-bundle.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="handheld bundle release workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign, the firmware settings, the "
                "annotation terms, the credits spent and left, every request on "
                "the receipt file and the working records on file. replay runs "
                "the notebook the way one recorded session's author ran it, on "
                "the evidence as it stood that day, and prints that session's "
                "notes and counts beside whatever the notebook returned. collect "
                "puts one capture request to the annotation desk: it returns the "
                "annotated rows it got, appends the receipt to "
                "capture_receipts.json and spends the credits; repeating a "
                "receipt_id returns the receipt already on file unbilled."
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
                    "duty_profile": {
                        "type": "string",
                        "description": "Duty profile the captures should come from.",
                    },
                    "firmware": {
                        "type": "string",
                        "description": "Firmware the units should be running.",
                    },
                    "condition": {
                        "type": "string",
                        "description": "Capture condition to ask for.",
                    },
                    "rows": {"type": "integer", "description": "How many captures to have annotated."},
                    "receipt_id": {
                        "type": "string",
                        "description": "A short label you choose for this request.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
