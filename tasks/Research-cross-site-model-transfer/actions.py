'Agent-visible tools for Research-cross-site-model-transfer.'

from __future__ import annotations

from typing import Any, Mapping

from tiganeval.taskkit import control_tools, experiment_tool, file_tools

from .project_tool import run_project


EDITABLE_PATHS = ("analysis.py", "support.py")


def get_actions() -> tuple[Mapping[str, Any], ...]:
    return (
        *file_tools(
            editable_paths=EDITABLE_PATHS,
            workspace_description="ticket triage reporting workspace",
        ),
        {
            "name": "run_project",
            "description": (
                "status prints the deployment, the intake settings, the review "
                "terms, the shipped model's manifest, the units spent and left, "
                "every review on the ledger and the working records on file. "
                "replay runs the notebook the way one recorded session's author "
                "ran it, on the evidence as it stood that day, and prints that "
                "session's notes and counters beside whatever the notebook "
                "returned. collect puts one review request through a channel: it "
                "returns the reviewed rows it got, appends the receipt to "
                "label_ledger.json and spends the units; repeating a receipt_id "
                "returns the receipt already on the ledger unbilled."
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
                    "site": {"type": "string", "description": "Centre the reviews are bought at."},
                    "channel": {"type": "string", "enum": ["queue", "export"]},
                    "rows": {"type": "integer", "description": "How many tickets to have reviewed."},
                    "prior_contacts_min": {
                        "type": "integer",
                        "description": "Lowest prior-contact count to ask for; leave out for no floor.",
                    },
                    "prior_contacts_max": {
                        "type": "integer",
                        "description": "Highest prior-contact count to ask for; leave out for no ceiling.",
                    },
                    "receipt_id": {
                        "type": "string",
                        "description": "A short label you choose for this review request.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
