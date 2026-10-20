"""Helpers for the QR-40 qualification notebook."""

from math import log, sqrt

TARGET = 0.10


def block_scales(context, receipts):
    """What each batch's own block readings say its bench's console does.

    The dead-weight block is one physical part at a known pressure, so the
    reading a bench writes for it is that bench's own factor. It goes on at
    each end of a batch and the two readings are averaged; a chamber session
    carries its own pair on its receipt.
    """

    block = float(context["block_bar"])
    scales = {}
    for row in context["bench_sheet"]:
        readings = [float(item) for item in row["block_readings_bar"]]
        scales[str(row["batch"])] = (sum(readings) / len(readings)) / block
    for entry in receipts:
        readings = [float(item) for item in entry.get("block_readings_bar") or ()]
        if readings:
            scales[str(entry["booking_id"])] = (sum(readings) / len(readings)) / block
    return scales


def unit_rows(context, receipts):
    """Every coupling the review holds, with where it came from."""

    rows = []
    for row in context["runs"]:
        rows.append(dict(row, source="batch_table"))
    for entry in receipts:
        readings = list(entry.get("readings_bar") or ())
        results = list(entry.get("results") or ())
        for reading, result in zip(readings, results):
            rows.append(
                {
                    "unit_id": f"{entry['booking_id']}-{len(rows)}",
                    "batch": str(entry["booking_id"]),
                    "bench": str(entry["bench"]),
                    "cartridge": str(entry["cartridge"]),
                    "reading_bar": float(reading),
                    "dwell_min": int(entry["dwell_min"]),
                    "result": str(result),
                    "source": "receipt",
                }
            )
    return rows


def counted_rows(context, receipts):
    """The rows that carry a pressure at the hold the plan is written against.

    Three kinds of row are left out. A block check is not a coupling. A row
    held for anything but the plan's own minutes sits at no level on this
    ladder, whatever cartridge it names. And a row that came back sitting on
    the console's sticker figure says the pressure was at least that and does
    not say what it was.
    """

    span = float(context["sticker_span_bar"])
    hold = int(context["plan_hold_min"])
    kept = []
    for row in unit_rows(context, receipts):
        if str(row["result"]) not in ("leak", "hold"):
            continue
        if int(row["dwell_min"]) != hold:
            continue
        if float(row["reading_bar"]) >= span - 1e-9:
            continue
        kept.append(row)
    return kept


def ladder(context, receipts):
    """(gauge pressure, units, leaks) for every cartridge the ladder counts.

    A cartridge is one level however many batches ran it, so its units add up
    across them; each row's console figure is put back into the gauge's bar
    with its own batch's factor before the level's pressure is taken.
    """

    scales = block_scales(context, receipts)
    table = {}
    for row in counted_rows(context, receipts):
        scale = scales.get(str(row["batch"]), 1.0)
        entry = table.setdefault(str(row["cartridge"]), [0.0, 0, 0])
        entry[0] += float(row["reading_bar"]) / scale
        entry[1] += 1
        entry[2] += 1 if str(row["result"]) == "leak" else 0
    return sorted(
        (total / units, units, leaks) for total, units, leaks in table.values() if units
    )


def logit(value):
    return log(value / (1.0 - value))


def line(levels):
    """A straight line through the ladder's log-odds, weighted by its units."""

    s0 = s1 = s2 = t0 = t1 = 0.0
    for pressure, units, leaks in levels:
        fraction = min(max((leaks + 0.5) / (units + 1.0), 1e-6), 1.0 - 1e-6)
        weight = units * fraction * (1.0 - fraction)
        value = logit(fraction)
        s0 += weight
        s1 += weight * pressure
        s2 += weight * pressure * pressure
        t0 += weight * value
        t1 += weight * value * pressure
    determinant = s0 * s2 - s1 * s1
    intercept = (s2 * t0 - s1 * t1) / determinant
    slope = (s0 * t1 - s1 * t0) / determinant
    return intercept, slope, s2 / determinant, s0 / determinant, -s1 / determinant


def crossing(levels, target=TARGET):
    intercept, slope, _a, _b, _c = line(levels)
    return (logit(target) - intercept) / slope


def half_width(levels, target=TARGET):
    """Two standard errors of the crossing, off the units the ladder counted."""

    intercept, slope, var_a, var_b, cov_ab = line(levels)
    value = (logit(target) - intercept) / slope
    variance = (var_a + value * value * var_b + 2.0 * value * cov_ab) / (slope * slope)
    return 2.0 * sqrt(max(variance, 0.0))


# -- the chamber's own arithmetic -------------------------------------------


def hours_left(context, receipts):
    granted = float(context["budget"]["chamber_hours_granted"])
    return round(granted - sum(float(item["hours_charged"]) for item in receipts), 3)


def stores_left(context, receipts):
    left = {batch: int(units) for batch, units in context["stores"].items()}
    for entry in receipts:
        batch = str(entry.get("batch") or "")
        if batch in left:
            left[batch] -= int(entry.get("units_returned") or 0)
    return left


def next_day(context, receipts):
    days = list(context["review_days"])
    return days[len(receipts)] if len(receipts) < len(days) else None


def bench_is_out(context, bench, day):
    window = context["bench_out_of_service"].get(str(bench))
    return bool(window) and day is not None and str(window[0]) <= str(day) <= str(window[1])


def readable_cartridges(context):
    """The cartridges the console has ever given a pressure for.

    A cartridge whose every row came back sitting on the sticker figure
    returns no pressure at all, so an hour spent on it buys no level.
    """

    span = float(context["sticker_span_bar"])
    readable = set()
    for row in context["runs"]:
        if str(row["result"]) not in ("leak", "hold"):
            continue
        if float(row["reading_bar"]) < span - 1e-9:
            readable.add(str(row["cartridge"]))
    return [name for name in context["cartridges_on_the_shelf"] if name in readable]


def cartridge_pressures(context, receipts):
    """The gauge pressure each readable cartridge has come back at."""

    scales = block_scales(context, receipts)
    span = float(context["sticker_span_bar"])
    table = {}
    for row in unit_rows(context, receipts):
        if str(row["result"]) not in ("leak", "hold"):
            continue
        if float(row["reading_bar"]) >= span - 1e-9:
            continue
        scale = scales.get(str(row["batch"]), 1.0)
        entry = table.setdefault(str(row["cartridge"]), [0.0, 0])
        entry[0] += float(row["reading_bar"]) / scale
        entry[1] += 1
    return {name: total / units for name, (total, units) in table.items() if units}


def bracketing(context, receipts):
    """The two cartridges the crossing sits between on the ladder as it stands."""

    value = crossing(ladder(context, receipts))
    pressures = cartridge_pressures(context, receipts)
    below = [name for name, bar in pressures.items() if bar <= value]
    above = [name for name, bar in pressures.items() if bar > value]
    out = []
    if below:
        out.append(max(below, key=lambda name: pressures[name]))
    if above:
        out.append(min(above, key=lambda name: pressures[name]))
    return out
