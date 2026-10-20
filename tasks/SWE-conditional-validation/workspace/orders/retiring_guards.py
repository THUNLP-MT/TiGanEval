"""The hand-written pair checks the API still runs, one function per entity.

The API calls the function for the entity on the item the parser hands it, and
refuses the write when the function comes back with anything. Each one was
written by hand as a pair came up and covers only the pairs somebody got round
to, which is what the `required_when` declarations in `entities/` are meant to
replace.
"""

from __future__ import annotations

from typing import Any, Mapping


def check_order(item: Mapping[str, Any]) -> tuple[str, ...]:
    """What is missing from one order."""

    missing: list[str] = []
    for name in ("order_id", "status", "currency"):
        if item.get(name) is None:
            missing.append(name)
    if item.get("payment_method") in ("card", "wallet") and item.get("authorisation_id") is None:
        missing.append("authorisation_id")
    return tuple(missing)


def check_refund(item: Mapping[str, Any]) -> tuple[str, ...]:
    """What is missing from one refund."""

    missing: list[str] = []
    for name in ("refund_id", "state", "amount"):
        if item.get(name) is None:
            missing.append(name)
    route = item.get("route")
    if isinstance(route, Mapping):
        if route.get("channel") in ("bank",) and route.get("account_ref") is None:
            missing.append("route.account_ref")
    return tuple(missing)


GUARDS = {"order": check_order, "refund": check_refund}
