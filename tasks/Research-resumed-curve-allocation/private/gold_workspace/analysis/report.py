"""The weekly allocation note for a sweep window with hours still to place."""

from analysis.support import (
    STOP_BELOW_HOURS,
    collection_lines,
    hours_left,
    hours_used,
    landings,
    open_node,
    segment_lines,
)


def analyze(context, ledger):
    found = landings(context, ledger)
    best = found[0] if found else None
    interval = None
    if best is not None:
        half = best["half_width"]
        interval = [best["end_loss"] - half, best["end_loss"] + half]
    return {
        "funded_run": best["config_id"] if best else None,
        "end_loss": best["end_loss"] if best else None,
        "end_loss_range": interval,
        "segments": segment_lines(context),
        "collections": collection_lines(ledger),
        "hours_used": hours_used(ledger),
        "hours_left": hours_left(context, ledger),
    }


def next_collection(context, ledger):
    """Put the hours where they separate the two runs that can still win."""

    left = hours_left(context, ledger)
    if left < STOP_BELOW_HOURS:
        return "stop"
    found = landings(context, ledger)
    if len(found) < 2:
        return "stop"
    node, _rate = open_node(context)
    window = context.get("cluster", {}).get("job_hours", {})
    longest = int(window.get("max") or 16)
    shortest = int(window.get("min") or 4)
    each = min(longest, left // 2)
    if each < shortest:
        return "stop"
    return {
        "jobs": [
            {"config_id": entry["config_id"], "node_type": node, "hours": each}
            for entry in found[:2]
        ]
    }
