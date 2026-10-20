'Agent-visible tools for Research-scaling-sweep-extrapolation.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="scaling sweep readout workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the sweep, the queue's terms, the compute units "
                "spent and left, the shard and block tables, every job on the "
                "receipt stream and the sessions on record. replay runs the "
                "notebook the way one recorded session's operator ran it, on the "
                "summary table as it stood that day, and prints that session's "
                "notes and rows beside whatever the notebook returned. collect "
                "books one training job at a width, an example count, a learning "
                "rate and a validation shard; it returns the final loss and the "
                "curve, appends the receipt to sweep_receipts.json and charges the "
                "grant. Repeating a job_id returns the receipt already on the "
                "stream without charging again."
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
                    "width": {
                        "type": "integer",
                        "minimum": 8,
                        "maximum": 4096,
                        "description": "Model width to train at.",
                    },
                    "data": {
                        "type": "integer",
                        "minimum": 500,
                        "maximum": 4000000,
                        "description": "Training examples for the job; the trainer runs one pass at the queue's batch size.",
                    },
                    "learning_rate": {"type": "number", "description": "Learning rate for the job."},
                    "val_shard": {
                        "type": "string",
                        "description": "Validation shard id to score the job on, as listed in sweep_context.json.",
                    },
                    "job_id": {
                        "type": "string",
                        "description": "A short label you choose for this reservation.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
