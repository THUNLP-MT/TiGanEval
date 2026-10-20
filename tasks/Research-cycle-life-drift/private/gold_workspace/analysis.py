"""The cycle-life study notebook: the September call and the next booking."""

from support import (
    arms, effect_range, hours_left, qualification_bay, retirement_cycle,
)


def analyze(context, receipts):
    sessions = {}
    for receipt in receipts:
        cycles = {
            cell["cell_id"]: retirement_cycle(context, receipt, cell)
            for cell in receipt["observed"]["cells"]
        }
        sessions[receipt["session_id"]] = {
            "cells": len(cycles),
            "channel_hours": receipt["channel_hours"],
            "retirement_cycles": cycles,
        }

    standard, stepped = arms(context, receipts)
    difference = None if standard is None or stepped is None else stepped - standard
    low, high = effect_range(context, receipts)
    bar = context["switch_threshold_cycles"]
    if low >= bar:
        decision = "switch"
    elif high < bar:
        decision = "keep"
    else:
        decision = None
    return {
        "sessions": sessions,
        "qualification_difference": difference,
        "difference_range": [low, high],
        "decision": decision,
    }


def next_collection(context, receipts):
    """The smallest booking that would close the question, while one is open."""

    low, high = effect_range(context, receipts)
    bar = context["switch_threshold_cycles"]
    if low >= bar or high < bar:
        return "stop"
    bay = qualification_bay(context)
    standard, stepped = arms(context, receipts)
    missing = [
        protocol
        for protocol, value in (("standard", standard), ("stepped", stepped))
        if value is None
    ]
    if not missing:
        return "stop"
    cells = context["cells_per_fixture"]
    if cells > len(context["rack"][bay]["channels"]):
        return "stop"
    if cells * context["channel_hours_per_cell"] > hours_left(context, receipts):
        return "stop"
    return {"bay": bay, "protocol": missing[0], "cells": cells}
