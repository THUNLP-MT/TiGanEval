"""What the rating engine does when it meets a recovery region.

This is the sketch Dinh left behind in June. It runs the rule body, tries it a
couple more times when something comes out of it, and prices the order at zero
when nothing works, so that one bad order does not take the run down with it.
It has never read `on_error`, `retry_on_error`, `guard` or `cleanup` from the
rulebook.
"""

from __future__ import annotations

from typing import Any

from .protocol import Env, Node, RunContext, eval_node


#: How many times the sketch runs a body before it gives up on the order.
TRIES = 3


def run_region(node: Node, env: Env, run: RunContext) -> Any:
    """Evaluate one recovery region and hand back the price it settled on."""

    body = node.children[0]
    for _ in range(TRIES):
        try:
            return eval_node(body, env, run)
        except Exception:  # noqa: BLE001 - the run has to reach the next order
            continue
    return 0.0
