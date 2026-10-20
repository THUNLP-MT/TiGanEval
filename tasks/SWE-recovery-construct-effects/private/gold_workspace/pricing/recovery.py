"""What the rating engine does when it meets a recovery region.

A region is one attempt at a price. Each attempt is transactional: the ledger
rows it committed are dropped unless it is the attempt whose value the region
hands back, and the reservations it took are given back before the next attempt
starts. The attempt that reaches a price is the attempt the order is priced
from, so an earlier attempt's fault is spent once a later one prices. Every
other branch of the region is inside the same reservation discipline: the
`on_error` branch gives back what it took before the `always` branch runs, and
the `always` branch gives back what it took before the region hands anything
back, and it runs however the region ends, so an order whose fault is leaving
is closed too and the rows the close wrote are discarded with the order's other
work. The region absorbs only the faults a rule body can produce; the step
budget and the desk's halt belong to the run and go straight through it.
Re-execution is spent from the order's attempt budget, so a region reached
through a fallback cannot buy attempts the order no longer has, and the
`always` branch has the last word on what the region hands back.
"""

from __future__ import annotations

from typing import Any

from .protocol import (
    EVALUATION_FAULTS,
    AttemptsExhausted,
    Env,
    Node,
    RunContext,
    eval_node,
)
from .triage import label_for


def run_region(node: Node, env: Env, run: RunContext) -> Any:
    """Evaluate one recovery region and hand back the price it settled on."""

    body, fallback, cleanup = node.children
    settings = dict(node.value or {})
    entry = env.mark()
    value: Any = None
    error: BaseException | None = None
    try:
        value, fault = _attempts(body, env, run, bool(settings.get("retry")))
        if fault is not None:
            env.discard_after(entry)
            if fallback is None or not _guard_takes(settings.get("guard"), fault):
                raise fault
            value = _branch(fallback, env, run)
    except BaseException as raised:  # noqa: BLE001 - re-raised below, after cleanup
        env.discard_after(entry)
        error = raised
    if cleanup is not None:
        try:
            _branch(cleanup, env, run)
        except BaseException as raised:
            env.discard_after(entry)
            raise raised from None
    if error is not None:
        # The close ran, and its own rows go with the rest of the order's work:
        # a region that hands back no price leaves the ledger where it found it.
        env.discard_after(entry)
        raise error
    return value


def _attempts(
    body: Node, env: Env, run: RunContext, retry: bool
) -> tuple[Any, BaseException | None]:
    """Run the body until it prices, until retrying it is pointless, or until
    the order has no attempt left. Every attempt gives back what it took.

    Whether the body is entered again is the rule's `retry_on_error` flag and
    the order's remaining budget; what the body raised does not decide it.
    """

    fault: BaseException | None = None
    while True:
        if run.attempts_left() <= 0:
            raise AttemptsExhausted(
                f"order {run.order_id} used all {run.max_attempts} attempts on {run.rule.name}"
            )
        mark, leases = env.mark(), env.lease_mark()
        try:
            value = eval_node(body, env, run)
        except EVALUATION_FAULTS as raised:
            env.close_since(leases)
            fault = raised
            if retry and run.attempts_left() > 0:
                env.discard_after(mark)
                continue
            return None, fault
        except BaseException:
            env.close_since(leases)
            raise
        env.close_since(leases)
        return value, None


def _branch(node: Node, env: Env, run: RunContext) -> Any:
    """Evaluate one branch of a region, giving back what that branch reserved."""

    leases = env.lease_mark()
    try:
        return eval_node(node, env, run)
    finally:
        env.close_since(leases)


def _guard_takes(guard: Any, fault: BaseException) -> bool:
    """Whether this region's `on_error` branch is meant for this fault."""

    return guard is None or str(guard) == label_for(fault)
