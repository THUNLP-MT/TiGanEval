"""What the rating engine does when it meets a recovery region.

Dinh's sketch, finished the way the ticket asks: when a rule body blows up the
order falls back to the rule's own `on_error` value instead of to zero, the
rules flagged `retry_on_error` are tried again first, and a rule that names a
`guard` only falls back for the incidents that label covers.
"""

from __future__ import annotations

from typing import Any

from .protocol import Env, Node, RunContext, eval_node
from .triage import label_for


#: How many times a rule flagged for retrying is tried before it falls back.
TRIES = 3


def run_region(node: Node, env: Env, run: RunContext) -> Any:
    """Evaluate one recovery region and hand back the price it settled on."""

    body, fallback, _cleanup = node.children
    settings = dict(node.value or {})
    tries = TRIES if settings.get("retry") else 1
    last: BaseException | None = None
    for _ in range(tries):
        try:
            return eval_node(body, env, run)
        except Exception as raised:  # noqa: BLE001 - the run has to reach the next order
            last = raised
    guard = settings.get("guard")
    if fallback is None or (guard is not None and str(guard) != label_for(last)):
        raise last if last is not None else RuntimeError("the rule produced no price")
    return eval_node(fallback, env, run)
