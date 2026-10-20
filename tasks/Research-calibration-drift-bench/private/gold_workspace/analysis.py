"""The bushing qualification notebook."""

from math import exp, sqrt

from support import (
    PART,
    RIGS,
    SUPPLIERS,
    cell_counts,
    hours_left,
    lot_levels,
    lots_of,
    mean,
    pairing,
    parts_in_stores,
    rig_hours_left,
    t_point,
    variance,
)


def analyze(context, receipts):
    levels, _step, _scaled = lot_levels(context, receipts)
    by_supplier = {
        supplier: [levels[lot] for lot in lots_of(context, supplier) if lot in levels]
        for supplier in SUPPLIERS
    }
    ratio = None
    span = None
    if all(by_supplier[supplier] for supplier in SUPPLIERS):
        gap = mean(by_supplier["B"]) - mean(by_supplier["A"])
        ratio = exp(gap)
        spread = 0.0
        df = 0
        for supplier in SUPPLIERS:
            count = len(by_supplier[supplier])
            value = variance(by_supplier[supplier])
            if value is not None:
                spread += value / count
                df += count - 1
        if spread > 0 and df > 0:
            half = t_point(df) * sqrt(spread)
            span = [exp(gap - half), exp(gap + half)]
    return {
        "wear_rate_ratio": ratio,
        "ratio_range": span,
        "sessions_used": _sessions_used(context, receipts),
        "measurements": [
            {
                "run_id": entry["run_id"],
                "rig": entry["rig"],
                "kind": entry["observed"]["kind"],
                "reading_um": entry["observed"]["reading_um"],
            }
            for entry in receipts
        ],
    }


def _sessions_used(context, receipts):
    """Part sessions behind the number, by supplier. The block is not a part."""

    counts = {supplier: 0 for supplier in SUPPLIERS}
    for row in context["sessions"]:
        counts[str(row["supplier"])] += 1
    for entry in receipts:
        if entry["observed"]["kind"] == PART and entry.get("supplier") in counts:
            counts[str(entry["supplier"])] += 1
    return counts


def next_collection(context, receipts):
    """Book the hours on parts that put their lot on both rigs.

    Everything else about the campaign is settled by the parts already run; what
    is not is how much lower rig 2 reads for the same part, and only a lot with
    parts on both rigs says anything about that.
    """

    counts = dict(cell_counts(context, receipts))
    stock = parts_in_stores(context, receipts)
    left = hours_left(context, receipts)
    rig_left = {rig: rig_hours_left(context, receipts, rig) for rig in RIGS}
    cost = float(context["booking"]["hours_per_part_session"])
    booked = []
    while stock and left >= cost:
        best = None
        for item in stock:
            lot = str(item["lot"])
            standing = pairing(counts, lot)
            for rig in RIGS:
                if rig_left[rig] < cost:
                    continue
                counts[(lot, rig)] = counts.get((lot, rig), 0) + 1
                gained = pairing(counts, lot) - standing
                counts[(lot, rig)] -= 1
                if best is None or gained > best[0]:
                    best = (gained, item, rig)
        if best is None or best[0] <= 0:
            break
        _gained, item, rig = best
        lot = str(item["lot"])
        counts[(lot, rig)] = counts.get((lot, rig), 0) + 1
        booked.append({"rig": rig, "part": str(item["part"])})
        stock = [entry for entry in stock if entry["part"] != item["part"]]
        left -= cost
        rig_left[rig] -= cost
    return booked or "stop"
