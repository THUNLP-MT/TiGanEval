"""The order-fulfilment workflow this service runs, as the engine reads it.

Frozen: the floor tooling raises these events and the audit reader is built
against these state and field names. ``data`` declares a state's own fields as
``[type, default]``; ``resume_points`` declare where an order that was put on
hold comes back in, and how far below that state the resume point reaches.
"""

from __future__ import annotations

from typing import Any, Mapping


ORDER_FLOW: Mapping[str, Any] = {
    "id": "order_flow",
    "initial": "Intake",
    "states": {
        "Intake": {"parent": None, "data": {}},
        "Fulfilling": {
            "parent": None,
            "initial": "Picking",
            "data": {
                "order_id": ["str", ""],
                "attempts": ["int", 0],
                "packed": ["list", []],
            },
        },
        "Picking": {
            "parent": "Fulfilling",
            "initial": "Scanning",
            "data": {"lines": ["list", []], "cursor": ["int", 0]},
        },
        "Scanning": {
            "parent": "Picking",
            "data": {"scans": ["list", []], "attempts": ["int", 0]},
        },
        "Reserving": {"parent": "Picking", "data": {"holds": ["list", []]}},
        "Packing": {"parent": "Fulfilling", "data": {"cartons": ["list", []]}},
        "Holding": {"parent": None, "data": {}},
        "Dispatched": {"parent": None, "data": {}},
    },
    "resume_points": {
        "carry_on": {"state": "Fulfilling", "kind": "full"},
        "replan": {"state": "Fulfilling", "kind": "direct"},
    },
    "transitions": (
        {"event": "accepted", "source": "Intake", "target": "Fulfilling"},
        {"event": "rescan", "source": "Scanning", "target": "Scanning", "internal": True},
        {"event": "recount", "source": "Scanning", "target": "Scanning", "internal": True},
        {"event": "reserved", "source": "Scanning", "target": "Reserving"},
        {"event": "retry", "source": "Reserving", "target": "Scanning"},
        {"event": "shelf", "source": "Reserving", "target": "Reserving", "internal": True},
        {"event": "recheck", "source": "Reserving", "target": "Reserving"},
        {"event": "picked", "source": "Picking", "target": "Packing"},
        {"event": "hold", "source": "Fulfilling", "target": "Holding"},
        {"event": "carry_on", "source": "Holding", "target": "Fulfilling", "resume": "carry_on"},
        {"event": "replan", "source": "Holding", "target": "Fulfilling", "resume": "replan"},
        {"event": "shipped", "source": "Packing", "target": "Dispatched"},
    ),
    "callbacks": {
        # What the floor's handlers do at each point of the flow.
        "enter:Fulfilling": (("set", "order_id", "@order"),),
        "on:rescan": (("bump", "attempts", 1), ("append", "scans", "@label")),
        "on:recount": (
            # Written by the shelf team after the November stock count.
            ("bump_in", "Picking", "atempts", 1),
            ("set_in", "Reserving", "holds", ["recount"]),
            ("set", "cursor", "seven"),
        ),
        "on:reserved": (("carry", "lines", "scans"),),
        "exit:Scanning": (("touch", "cursor"),),
        "enter:Reserving": (("bump", "cursor", 1),),
        "on:shelf": (("append", "holds", "@sku"),),
        "on:recheck": (("bump", "cursor", 1),),
        "on:retry": (("bump", "attempts", 1),),
        "exit:Picking": (("carry", "packed", "lines"),),
        "enter:Packing": (("append", "cartons", "@carton"),),
        "exit:Fulfilling": (("touch", "order_id"),),
    },
}


__all__ = ("ORDER_FLOW",)
