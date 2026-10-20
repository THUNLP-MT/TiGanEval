"""The auto-clear readout for one listing review queue."""

from support import (
    batches,
    combined,
    credits_used,
    evidence,
    half_width,
    open_cells,
    recommended_cut,
)


def analyze(context, receipts):
    found = evidence(context, receipts)
    centre = combined(found)
    spread = half_width(found)
    interval = None
    if centre is not None:
        interval = [max(0.0, centre - spread), min(100.0, centre + spread)]
    return {
        "escape_rate": centre,
        "escape_interval": interval,
        "recommended_cut": recommended_cut(context, receipts),
        "listings_adjudicated": sum(int(row["listings"]) for row in found.values()),
        "batches": batches(receipts),
        "credits_used": credits_used(receipts),
    }


def next_batch(context, receipts):
    """Book the cell that closes most of the stream nobody has an outcome for."""

    available = open_cells(context, receipts)
    if not available:
        return "stop"
    _, (channel, period), count, room = available[0]
    return {"channel": channel, "period": period, "listings": min(count, room)}
