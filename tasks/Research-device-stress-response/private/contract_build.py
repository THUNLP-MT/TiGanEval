'A second notebook, written from `full_information.md` and from nothing else.'

from __future__ import annotations


ANALYSIS = '''"""QR-40 report, built from the submission contract.

Every level of the ladder is one cartridge, and the level sits at the pressure
its own rows come back at rather than at the size in the cartridge's name. A
row joins its level in the gauge's bar, worked out from its own batch's two
dead-weight block readings against the block's certified pressure. Rows that came back on the console's
sticker figure carry no pressure and are left out; rows held for anything but
the plan's own minutes belong to a different question and are left out too.

Across the levels the log-odds of the leak fraction run straight against
pressure. The line is fitted by maximum likelihood over the counted couplings,
and the pressure where it reaches one in ten is the number. The range is two
standard errors of that pressure either side of it, off the same fit.
"""

from math import exp, log, sqrt

SOURCES = ("batch_table", "receipt")


def _logit(value):
    return log(value / (1.0 - value))


def _logistic(value):
    if value < -700.0:
        return 0.0
    if value > 700.0:
        return 1.0
    return 1.0 / (1.0 + exp(-value))


def _factors(context, receipts):
    """What each batch's own block readings say its bench's console does."""

    block = float(context["block_bar"])
    out = {}
    for row in context["bench_sheet"]:
        pair = [float(item) for item in row["block_readings_bar"]]
        out[str(row["batch"])] = (sum(pair) / len(pair)) / block
    for entry in receipts:
        pair = [float(item) for item in entry.get("block_readings_bar") or ()]
        if pair:
            out[str(entry["booking_id"])] = (sum(pair) / len(pair)) / block
    return out


def _rows(context, receipts):
    for row in context["runs"]:
        yield dict(row), "batch_table"
    for entry in receipts:
        readings = list(entry.get("readings_bar") or ())
        results = list(entry.get("results") or ())
        for reading, result in zip(readings, results):
            yield (
                {
                    "batch": str(entry["booking_id"]),
                    "bench": str(entry["bench"]),
                    "cartridge": str(entry["cartridge"]),
                    "reading_bar": float(reading),
                    "dwell_min": int(entry["dwell_min"]),
                    "result": str(result),
                },
                "receipt",
            )


def counted(context, receipts):
    """The rows that carry a pressure at the hold the plan is written against."""

    span = float(context["sticker_span_bar"])
    hold = int(context["plan_hold_min"])
    factors = _factors(context, receipts)
    kept = []
    for row, source in _rows(context, receipts):
        if str(row["result"]) not in ("leak", "hold"):
            continue
        if int(row["dwell_min"]) != hold:
            continue
        if float(row["reading_bar"]) >= span - 1e-9:
            continue
        kept.append(
            (
                str(row["cartridge"]),
                float(row["reading_bar"]) / factors.get(str(row["batch"]), 1.0),
                str(row["result"]),
                source,
            )
        )
    return kept


def ladder(context, receipts):
    """(pressure, couplings, leaks) for every cartridge the ladder counts."""

    table = {}
    for cartridge, pressure, result, _source in counted(context, receipts):
        entry = table.setdefault(cartridge, [0.0, 0, 0])
        entry[0] += pressure
        entry[1] += 1
        entry[2] += 1 if result == "leak" else 0
    return sorted(
        (total / units, units, leaks) for total, units, leaks in table.values() if units
    )


def _fit(levels):
    """Maximum likelihood straight line through the log-odds of the levels."""

    intercept, slope = _start(levels)
    covariance = None
    for _step in range(200):
        s0 = s1 = s2 = t0 = t1 = 0.0
        for pressure, units, leaks in levels:
            eta = max(-40.0, min(40.0, intercept + slope * pressure))
            mu = _logistic(eta)
            weight = max(units * mu * (1.0 - mu), 1e-9)
            target = eta + (leaks - units * mu) / weight
            s0 += weight
            s1 += weight * pressure
            s2 += weight * pressure * pressure
            t0 += weight * target
            t1 += weight * target * pressure
        determinant = s0 * s2 - s1 * s1
        moved_a = (s2 * t0 - s1 * t1) / determinant
        moved_b = (s0 * t1 - s1 * t0) / determinant
        done = abs(moved_a - intercept) < 1e-10 and abs(moved_b - slope) < 1e-12
        intercept, slope = moved_a, moved_b
        covariance = (s2 / determinant, s0 / determinant, -s1 / determinant)
        if done:
            break
    return intercept, slope, covariance


def _start(levels):
    s0 = s1 = s2 = t0 = t1 = 0.0
    for pressure, units, leaks in levels:
        fraction = min(max((leaks + 0.5) / (units + 1.0), 1e-6), 1.0 - 1e-6)
        weight = units * fraction * (1.0 - fraction)
        value = _logit(fraction)
        s0 += weight
        s1 += weight * pressure
        s2 += weight * pressure * pressure
        t0 += weight * value
        t1 += weight * value * pressure
    determinant = s0 * s2 - s1 * s1
    return (s2 * t0 - s1 * t1) / determinant, (s0 * t1 - s1 * t0) / determinant


def crossing(context, receipts):
    levels = ladder(context, receipts)
    intercept, slope, covariance = _fit(levels)
    target = _logit(float(context["target_fraction"]))
    value = (target - intercept) / slope
    var_a, var_b, cov_ab = covariance
    variance = (var_a + value * value * var_b + 2.0 * value * cov_ab) / (slope * slope)
    return value, 2.0 * sqrt(max(variance, 0.0))


def analyze(context, receipts):
    value, spread = crossing(context, receipts)
    totals = {}
    for _cartridge, _pressure, result, source in counted(context, receipts):
        entry = totals.setdefault(source, [0, 0])
        entry[0] += 1
        entry[1] += 1 if result == "leak" else 0
    return {
        "crossing_bar": value,
        "crossing_range_bar": [value - spread, value + spread],
        "counted_units": [
            {"source": source, "units": units, "leaks": leaks}
            for source, (units, leaks) in sorted(totals.items())
        ],
        "sessions": [
            {
                "booking_id": entry["booking_id"],
                "bench": entry["bench"],
                "dwell_min": int(entry["dwell_min"]),
                "units": int(entry["units_returned"]),
                "leaks": list(entry.get("results") or ()).count("leak"),
                "hours_charged": float(entry["hours_charged"]),
            }
            for entry in receipts
        ],
    }


def _pressures(context, receipts):
    """The gauge pressure each cartridge the console reads has come back at."""

    span = float(context["sticker_span_bar"])
    factors = _factors(context, receipts)
    table = {}
    for row, _source in _rows(context, receipts):
        if str(row["result"]) not in ("leak", "hold"):
            continue
        if float(row["reading_bar"]) >= span - 1e-9:
            continue
        entry = table.setdefault(str(row["cartridge"]), [0.0, 0])
        entry[0] += float(row["reading_bar"]) / factors.get(str(row["batch"]), 1.0)
        entry[1] += 1
    return {name: total / units for name, (total, units) in table.items() if units}


def next_block(context, receipts):
    hold = int(context["plan_hold_min"])
    cost = float(context["budget"]["hours_at_the_plan_hold"])
    granted = float(context["budget"]["chamber_hours_granted"])
    spent = sum(float(entry["hours_charged"]) for entry in receipts)
    left = round(granted - spent, 3)
    stock = {batch: int(units) for batch, units in context["stores"].items()}
    for entry in receipts:
        if str(entry.get("batch")) in stock:
            stock[str(entry["batch"])] -= int(entry.get("units_returned") or 0)
    days = list(context["review_days"])
    day = days[len(receipts)] if len(receipts) < len(days) else None
    if left < cost or day is None or not stock or max(stock.values()) < 1:
        return "stop"
    benches = []
    for name in sorted(context["benches"]):
        window = context["bench_out_of_service"].get(name)
        if window and str(window[0]) <= str(day) <= str(window[1]):
            continue
        benches.append(name)
    if not benches:
        return "stop"
    batch = max(sorted(stock), key=lambda name: stock[name])
    units = min(int(context["budget"]["ports_per_session"]), stock[batch])
    value, _spread = crossing(context, receipts)
    pressures = _pressures(context, receipts)
    below = [name for name, bar in pressures.items() if bar <= value]
    above = [name for name, bar in pressures.items() if bar > value]
    wanted = []
    if below:
        wanted.append(max(below, key=lambda name: pressures[name]))
    if above:
        wanted.append(min(above, key=lambda name: pressures[name]))
    if not wanted:
        return "stop"
    carried = {}
    for cartridge, _pressure, _result, _source in counted(context, receipts):
        carried[cartridge] = carried.get(cartridge, 0) + 1
    cartridge = min(wanted, key=lambda name: (carried.get(name, 0), name))
    return {
        "bench": benches[0],
        "batch": batch,
        "cartridge": cartridge,
        "dwell_min": hold,
        "units": int(units),
    }
'''

SUPPORT = '"""Nothing here: this build keeps everything in analysis.py."""\n'

FILES = {"analysis.py": ANALYSIS, "support.py": SUPPORT}
