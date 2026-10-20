'Agent-visible tools for Research-device-kinetics-discrimination.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="EM-9 soak qualification workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign, the plan's terms and caps, the "
                "decay catalogue, the chamber days spent and left, what the "
                "shop holds in spares, every block on the receipts and the "
                "working days on record. replay runs the notebook the way one "
                "recorded working day ran it, on the export as it stood then, "
                "and prints that day's notes, the module index and the export "
                "module by module beside whatever the notebook returned. "
                "collect puts one block in front of the chamber desk: it "
                "returns that block's spare modules with their incoming "
                "readings and every bench row it came back with, appends the "
                "receipt to soak_receipts.json and charges the days; a sheet "
                "the desk will not take comes back with the reason and the "
                "days are charged all the same; repeating a block_id returns "
                "the receipt already on the stream unbilled."
            ),
            "handler": run_project,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "replay", "collect"]},
                    "record": {
                        "type": "string",
                        "description": "Workspace-relative path of a day under project_records/.",
                    },
                    "drive_a": {
                        "type": "number",
                        "description": "Drive current, in amps, to hold the block at.",
                    },
                    "case_temp_c": {
                        "type": "number",
                        "description": "Case temperature, in degrees, to hold the block at.",
                    },
                    "ports": {
                        "type": "integer",
                        "description": "How many spare modules to put in the rig.",
                    },
                    "chamber_days": {
                        "type": "integer",
                        "description": "How many chamber days to run the block for.",
                    },
                    "lot": {
                        "type": "string",
                        "description": "Which lot of spares to draw the modules from.",
                    },
                    "block_id": {
                        "type": "string",
                        "description": "A short label you choose for this block.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
