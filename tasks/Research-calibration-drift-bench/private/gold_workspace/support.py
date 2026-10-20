"""Reading the bench: what the block says, and what the two rigs say about each other."""

from math import log, sqrt

SUPPLIERS = ("A", "B")
RIGS = (1, 2)
PART = "part"
REFERENCE = "reference"

#: Two-sided 95% points of Student's t, by degrees of freedom.
_T = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
      8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
      15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}


def t_point(df):
    if df <= 0:
        return 0.0
    if df in _T:
        return _T[df]
    return 1.96 if df > 20 else _T[1]


def mean(values):
    items = list(values)
    return sum(items) / len(items) if items else None


def variance(values):
    items = list(values)
    if len(items) < 2:
        return None
    centre = mean(items)
    return sum((item - centre) ** 2 for item in items) / (len(items) - 1)


def observations(context, receipts):
    """Every reading this campaign holds, with the bench-hours behind it.

    A rig's hours run on from the last time the house signed it off and start
    again at nothing when it does, so the table's own order gives each reading
    the hours its rig had run when it was taken. Sessions the campaign has paid
    for since the table was written carry on from where the table stopped.
    """

    part_hours = float(context["booking"]["hours_per_part_session"])
    block_hours = float(context["booking"]["hours_per_reference_run"])
    used = {}
    standing = {}
    rows = []
    for row in context["sessions"]:
        rig, calibration = int(row["rig"]), str(row["calibration"])
        running = used.get((rig, calibration), 0.0)
        if row.get("reference_um") is not None:
            rows.append({"rig": rig, "calibration": calibration, "kind": REFERENCE,
                         "hours": running, "reading": float(row["reference_um"]),
                         "lot": None, "supplier": None})
            running += block_hours
        rows.append({"rig": rig, "calibration": calibration, "kind": PART,
                     "hours": running, "reading": float(row["depth_um"]),
                     "lot": str(row["lot"]), "supplier": str(row["supplier"])})
        used[(rig, calibration)] = running + part_hours
        standing[rig] = (calibration, used[(rig, calibration)])
    for entry in receipts:
        rig = int(entry["rig"])
        calibration, running = standing.get(rig, (str(entry.get("calibration")), 0.0))
        observed = entry["observed"]
        rows.append({"rig": rig, "calibration": calibration,
                     "kind": str(observed["kind"]), "hours": running,
                     "reading": float(observed["reading_um"]),
                     "lot": entry.get("lot"), "supplier": entry.get("supplier")})
        standing[rig] = (calibration, running + float(entry["hours"]))
    return rows


def _line(points):
    """Intercept and slope of a straight line through (hours, reading) points."""

    if len(points) < 2:
        return (1.0, 0.0)
    centre_x = mean(x for x, _ in points)
    centre_y = mean(y for _, y in points)
    spread = sum((x - centre_x) ** 2 for x, _ in points)
    if spread <= 0:
        return (centre_y, 0.0)
    slope = sum((x - centre_x) * (y - centre_y) for x, y in points) / spread
    return (centre_y - slope * centre_x, slope)


def block_lines(rows):
    """One line per rig through the certified block's readings against hours."""

    lines = {}
    for rig in RIGS:
        points = [(row["hours"], row["reading"]) for row in rows
                  if row["rig"] == rig and row["kind"] == REFERENCE]
        lines[rig] = _line(points)
    return lines


def on_one_scale(rows):
    """Each part reading referred to a fresh calibration on its own rig."""

    lines = block_lines(rows)
    scaled = []
    for row in rows:
        if row["kind"] != PART:
            continue
        intercept, slope = lines[row["rig"]]
        factor = (intercept + slope * row["hours"]) / intercept if intercept else 1.0
        scaled.append(dict(row, level=log(row["reading"]) - log(factor)))
    return scaled


def cells(scaled):
    """{(lot, rig): the levels of that lot's parts that ran on that rig}."""

    grouped = {}
    for row in scaled:
        grouped.setdefault((row["lot"], row["rig"]), []).append(row["level"])
    return grouped


def fixture_step(scaled):
    """How much lower rig 2 reads than rig 1 for parts out of the same lot."""

    grouped = cells(scaled)
    lots = {row["lot"] for row in scaled}
    gaps = [mean(grouped[(lot, 2)]) - mean(grouped[(lot, 1)])
            for lot in lots
            if (lot, 1) in grouped and (lot, 2) in grouped]
    return mean(gaps) or 0.0 if gaps else 0.0


def lot_levels(context, receipts):
    """One level per lot, with both rigs' readings put on rig 1's fixture."""

    scaled = on_one_scale(observations(context, receipts))
    step = fixture_step(scaled)
    grouped = {}
    for row in scaled:
        grouped.setdefault(row["lot"], []).append(
            row["level"] - (step if row["rig"] == 2 else 0.0)
        )
    return {lot: mean(values) for lot, values in grouped.items()}, step, scaled


def lots_of(context, supplier):
    return [str(lot["lot"]) for lot in context["lots"] if lot["supplier"] == supplier]


# -- what the hours that are left can still buy -----------------------------


def hours_spent(receipts):
    return sum(float(entry["hours"]) for entry in receipts)


def hours_left(context, receipts):
    return float(context["booking"]["bench_hours_left"]) - hours_spent(receipts)


def rig_hours_left(context, receipts, rig):
    granted = float(context["booking"]["rig_hours_available"][str(rig)])
    return granted - sum(float(entry["hours"]) for entry in receipts
                         if int(entry["rig"]) == int(rig))


def parts_in_stores(context, receipts):
    run = {str(entry.get("part")) for entry in receipts if entry.get("part")}
    return [dict(item) for item in context["stores"] if str(item["part"]) not in run]


def cell_counts(context, receipts):
    """How many parts of each lot have run on each rig so far."""

    counts = {}
    for row in context["sessions"]:
        key = (str(row["lot"]), int(row["rig"]))
        counts[key] = counts.get(key, 0) + 1
    for entry in receipts:
        if entry["observed"]["kind"] != PART or not entry.get("lot"):
            continue
        key = (str(entry["lot"]), int(entry["rig"]))
        counts[key] = counts.get(key, 0) + 1
    return counts


def pairing(counts, lot):
    """What one lot contributes to the comparison between the two rigs.

    A lot says nothing about the two fixtures unless it has parts on both, and
    what it says is worth the smaller of its two sides.
    """

    first = counts.get((lot, 1), 0)
    second = counts.get((lot, 2), 0)
    return first * second / (first + second) if first + second else 0.0
