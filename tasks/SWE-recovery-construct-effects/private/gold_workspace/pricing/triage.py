"""The triage label one incident is filed under.

Operations groups the night's incidents by this label on the morning board, and
a rule's `guard` names the label its `on_error` branch is meant for. The engine
calls this once per fault, where the fault is raised.
"""

from __future__ import annotations

from typing import Any

from .protocol import ERROR_KINDS, OTHER_LABEL


def label_for(fault: Any) -> str:
    """The label this fault belongs under on the morning board.

    The class the engine raised decides it. Two orders that hit the same fault
    are one incident however differently the message reads.
    """

    for klass in type(fault).__mro__:
        if klass in ERROR_KINDS:
            return str(ERROR_KINDS[klass])
    return OTHER_LABEL
