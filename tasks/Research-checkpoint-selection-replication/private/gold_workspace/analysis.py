"""The release readout for one training campaign."""

from support import (
    differences,
    pairing_lot,
    settled_on,
    half_width,
    job_lines,
    mean,
    quietest_lot,
    shortlist,
    slices_used,
    table_best,
    units_left,
    unpaired_half_width,
    usable_units,
)


def analyze(context, ledger):
    model = str(context["release"]["model_id"])
    held = differences(ledger, model)
    if held:
        shipped = settled_on(held)
        gain = mean(held[shipped])
        spread = half_width(held[shipped])
    else:
        shipped = table_best(context)
        gain = None
        spread = unpaired_half_width(context, ledger, shipped)
    return {
        "shipped_checkpoint": shipped,
        "gain_points": gain,
        "gain_range": None if gain is None else [gain - spread, gain + spread],
        "jobs": job_lines(ledger),
        "units_left": units_left(context, ledger),
    }


def next_collection(context, ledger):
    """Put the shortlist and the released model on one lot, while the units last."""

    model = str(context["release"]["model_id"])
    price = int(context["compute"]["price_per_read"])
    cap = int(context["compute"]["job_cap_units"])
    held = differences(ledger, model)
    if held:
        # The number wants the rest of the lot the pair is already on: what is
        # left inside a job is each item's own luck on the rows it happened to
        # get, and that only comes down by reading more of the lot.
        best = settled_on(held)
        items = [best, model]
        ranking = None
        settled = pairing_lot(ledger, model, best)
    else:
        items = [*shortlist(context), model]
        settled = None
        # Three reads apiece separate a shortlist without spending the whole lot
        # on rows that will not be shipped; the rest of the lot goes on the one
        # that comes out ahead.
        ranking = 3

    lot = settled or quietest_lot(context, ledger)
    room_on_lot = int(context["lots"]["reads_per_lot"]) - slices_used(ledger, lot)
    while items:
        room = min(
            room_on_lot,
            usable_units(context, ledger) // (price * len(items)),
            cap // (price * len(items)),
        )
        if ranking is not None:
            room = min(room, ranking)
        if room >= 1:
            return {"kind": "reads", "lot": lot, "items": items, "repeats": int(room)}
        if len(items) <= 2:
            break
        items = [items[0], items[-1]]
    return "stop"
