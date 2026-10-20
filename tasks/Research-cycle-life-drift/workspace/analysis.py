"""The cycle-life study notebook: the September call and the next booking."""


def _mean(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def _retirement(context, cell):
    line = context["rated_capacity_ah"] * context["retirement_fraction"]
    for cycle, amp_hours in cell["checkpoints"]:
        if amp_hours < line:
            return cycle
    return None


def _by_protocol(context, receipts):
    gathered = {}
    for receipt in receipts:
        for cell in receipt["observed"]["cells"]:
            gathered.setdefault(receipt["protocol"], []).append(_retirement(context, cell))
    return gathered


def analyze(context, receipts):
    sessions = {}
    for receipt in receipts:
        cycles = {
            cell["cell_id"]: _retirement(context, cell)
            for cell in receipt["observed"]["cells"]
        }
        sessions[receipt["session_id"]] = {
            "cells": len(cycles),
            "channel_hours": receipt["channel_hours"],
            "retirement_cycles": cycles,
        }
    gathered = _by_protocol(context, receipts)
    standard = _mean(gathered.get("standard", []))
    stepped = _mean(gathered.get("stepped", []))
    difference = None if standard is None or stepped is None else stepped - standard
    decision = "switch" if difference is not None and difference >= context[
        "switch_threshold_cycles"] else "keep"
    return {
        "sessions": sessions,
        "qualification_difference": difference,
        "decision": decision,
    }


def next_collection(context, receipts):
    """Put the next fixture on whichever charge is ahead."""

    gathered = _by_protocol(context, receipts)
    standard = _mean(gathered.get("standard", []))
    stepped = _mean(gathered.get("stepped", []))
    ahead = "stepped" if (stepped or 0) >= (standard or 0) else "standard"
    return {"bay": sorted(context["rack"])[0], "protocol": ahead,
            "cells": context["cells_per_fixture"]}
