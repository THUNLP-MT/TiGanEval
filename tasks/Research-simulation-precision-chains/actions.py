'Agent-visible tools for Research-simulation-precision-chains.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="reservation capacity study workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the study, the charter's terms, the compute steps "
                "charged and left, every job on the receipt stream, a per-run "
                "summary of the stored files and the working sessions on record. "
                "replay runs the notebook the way one recorded session ran it, on "
                "the files as they stood that day, and prints that session's notes "
                "and per-run summary beside whatever the notebook returned. "
                "collect puts one job to the compute console: give a chain_id to "
                "carry a stored run on, or start_new to open a fresh one, with a "
                "number of steps. It returns the steps the console ran, writes "
                "them onto that run's file in chains/, updates chain_manifest.csv, "
                "appends the receipt to collection_receipts.json and charges the "
                "grant; it "
                "refuses a job under the minimum, over the cap or on a run it does "
                "not have, and charges the refusal fee. Repeating a call_id returns "
                "the receipt already on the stream unbilled."
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
                    "chain_id": {
                        "type": "string",
                        "description": "Stored run to carry on, as the manifest names it.",
                    },
                    "start_new": {
                        "type": "boolean",
                        "description": "true opens a run from a fresh dispersed start instead.",
                    },
                    "steps": {"type": "integer", "description": "How many sampler steps to run."},
                    "call_id": {
                        "type": "string",
                        "description": "A short label you choose for this job.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=60.0),
        *control_tools(),
    )
