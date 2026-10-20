"""The triage label one incident is filed under.

Operations groups the night's incidents by this label on the morning board, and
a rule's `guard` names the label its `on_error` branch is meant for. The engine
calls this once per fault, where the fault is raised.
"""

from __future__ import annotations

from typing import Any


#: Dinh's first pass: read the label off the wording of the message.
HINTS = (
    ("out of range", "lookup"),
    ("no value for", "lookup"),
    ("cannot read", "conversion"),
    ("refused", "declared"),
    ("attempts", "exhausted"),
)


def label_for(fault: Any) -> str:
    """The label this fault belongs under on the morning board."""

    message = str(fault)
    for hint, label in HINTS:
        if hint in message:
            return label
    return "other"
