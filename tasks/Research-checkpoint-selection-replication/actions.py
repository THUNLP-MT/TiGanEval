'Agent-visible tools for Research-checkpoint-selection-replication.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="ranking release readout workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the campaign, the release it is measured against, "
                "the lots the desk can score on, the compute terms, every job on "
                "the receipt stream and the working records on file. replay runs "
                "the notebook the way one recorded session's author ran it, on the "
                "evidence as it stood that day, and prints that session's notes "
                "beside whatever the notebook returned. collect sends one job to "
                "the evaluation desk: a reads job scores the items you name on one "
                "lot, a train job queues more training. Either way it appends the "
                "sealed receipt to ledger/receipts.jsonl and spends the units; a "
                "job the desk will not run is handed back with the queue fee "
                "charged, and repeating a job_id returns the receipt already on "
                "the stream unbilled."
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
                    "kind": {
                        "type": "string",
                        "enum": ["reads", "train"],
                        "description": "reads scores items on a lot; train queues training runs.",
                    },
                    "lot": {
                        "type": "string",
                        "description": "The validation lot a reads job runs on.",
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Checkpoint ids such as r06@13500, or the released "
                            "model id, to be scored in this job."
                        ),
                    },
                    "repeats": {
                        "type": "integer",
                        "description": "How many times to read each item in this job.",
                    },
                    "job_id": {
                        "type": "string",
                        "description": "A short label you choose for this job.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
