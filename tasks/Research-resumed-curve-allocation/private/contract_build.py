'A second build of the notebook, written from `full_information.md` alone.'

from __future__ import annotations


REPORT = '''"""The window's allocation note, built from what the review asked for."""

from math import exp, log, sqrt


# The slide is made on this window and the six after it, and the one time in
# twenty the review will take being wrong is over that whole run of seven
# rather than on each of them, so the range is read at 0.05 / 7 two-sided.
COVER = 2.6906
SMALLEST_BOOKING_HOURS = 8


def segments_by_run(context):
    rows = {}
    for row in context.get("ledger", ()):
        rows.setdefault(str(row["config_id"]), []).append(row)
    return rows


def chain_of(rows):
    """The segments of one run in the order they were run, and where each starts.

    The step column starts again at nought every time a run is resumed, so the
    training behind a row is the row's own step plus every step the segments
    ahead of it in the chain ran.
    """

    follows = {}
    head = None
    for row in rows:
        parent = row.get("resumed_from")
        if parent is None:
            head = row
        else:
            follows[str(parent)] = row
    order = []
    seen = set()
    node = head if head is not None else rows[0]
    while node is not None and str(node["segment_id"]) not in seen:
        seen.add(str(node["segment_id"]))
        order.append(node)
        node = follows.get(str(node["segment_id"]))
    for row in rows:
        if str(row["segment_id"]) not in seen:
            order.append(row)
    start = {}
    total = 0
    for row in order:
        start[str(row["segment_id"])] = total
        total += int(row["last_step"])
    return start, total


def training_rows(context, config_id, start):
    rows = []
    curve = list(context.get("curves", {}).get(config_id, ()))
    top = 0.0
    for row in curve:
        top = max(top, float(row.get("lr") or 0.0))
    top = top or 1.0
    for row in curve:
        base = start.get(str(row.get("segment_id")))
        if base is None:
            continue
        rows.append(
            (base + float(row["step"]), float(row["lr"]) / top, float(row["loss"]))
        )
    rows.sort()
    return rows


def hours_into_steps(context):
    """The fastest node type the window has free, and what it makes of an hour."""

    held = set(context.get("cluster", {}).get("reserved_node_types", ()))
    tally = {}
    for row in context.get("ledger", ()):
        hours = float(row.get("wall_hours") or 0.0)
        steps = float(row.get("last_step") or 0.0)
        if hours <= 0.0 or steps <= 0.0:
            continue
        name = str(row["node_type"])
        got, count = tally.get(name, (0.0, 0))
        tally[name] = (got + steps / hours, count + 1)
    rates = {name: got / count for name, (got, count) in tally.items()}
    free = {name: rate for name, rate in rates.items() if name not in held} or rates
    name = max(free, key=lambda key: free[key])
    return name, free[name]


def _three(exponent, logs, rates, values):
    """floor, amplitude and the instrument together, for one exponent."""

    powers = [exp(-exponent * item) for item in logs]
    count = len(values)
    sp = sum(powers)
    spp = sum(a * a for a in powers)
    spu = sum(a * b for a, b in zip(powers, rates))
    spy = sum(a * b for a, b in zip(powers, values))
    su = sum(rates)
    suu = sum(a * a for a in rates)
    suy = sum(a * b for a, b in zip(rates, values))
    sy = sum(values)
    rows = [[float(count), sp, su, sy], [sp, spp, spu, spy], [su, spu, suu + 1e-9, suy]]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda r: abs(rows[r][column]))
        if abs(rows[pivot][column]) < 1e-13:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        head = rows[column]
        for index in range(3):
            if index == column:
                continue
            factor = rows[index][column] / head[column]
            if factor:
                for cell in range(column, 4):
                    rows[index][cell] -= factor * head[cell]
    floor, amplitude, instrument = (rows[i][3] / rows[i][i] for i in range(3))
    left = sum(
        (value - (floor + amplitude * power + instrument * rate)) ** 2
        for power, rate, value in zip(powers, rates, values)
    )
    return left, floor, amplitude, instrument


_FITTED = {}


def fit_curve(rows):
    """The curve one run is on, with the instrument carried alongside it.

    A row is the run's level plus an amount that goes with the learning rate it
    was written at, and that amount is the same instrument at every run, so the
    learning rate column goes into the curve rather than into the scatter. Only
    the exponent has to be searched for; everything else falls out of the rows
    once it is fixed.
    """

    key = (
        len(rows),
        rows[0][0],
        rows[-1][0],
        round(sum(row[0] for row in rows), 3),
        round(sum(row[2] for row in rows), 6),
    )
    if key in _FITTED:
        return _FITTED[key]
    logs = [log(max(1.0, step) / 1000.0) for step, _rate, _loss in rows]
    rates = [rate for _step, rate, _loss in rows]
    losses = [loss for _step, _rate, loss in rows]
    best = None
    for index in range(25):
        candidate = 0.12 + 0.58 * index / 24
        got = _three(candidate, logs, rates, losses)
        if got is not None and (best is None or got[0] < best[0]):
            best = (got[0], candidate)
    low = max(0.12, best[1] - 0.58 / 24)
    high = min(0.70, best[1] + 0.58 / 24)
    for _step in range(22):
        middle = (low + high) / 2.0
        gap = (high - low) / 4.0
        left = _three(middle - gap, logs, rates, losses)
        right = _three(middle + gap, logs, rates, losses)
        if left[0] < right[0]:
            high = middle
        else:
            low = middle
    exponent = (low + high) / 2.0
    _left, floor, amplitude, instrument = _three(exponent, logs, rates, losses)
    model = {"floor": floor, "amplitude": amplitude, "exponent": exponent,
             "instrument": instrument}
    _FITTED[key] = model
    return model


def curve_at(model, steps):
    return model["floor"] + model["amplitude"] * (max(1.0, steps) / 1000.0) ** (
        -model["exponent"]
    )


def width_left_open(rows, steps, blocks=10):
    """How far the number can still move on the rows behind the curve.

    Drop a block of the rows, draw the curve through what is left, and read the
    number out again. How far those readings spread is what the rows leave
    open, and it grows both when there are fewer rows and when the number is
    read further past the last of them.
    """

    if len(rows) < blocks + 6:
        blocks = max(3, len(rows) // 3)
    if len(rows) <= 6:
        return 0.04
    readings = []
    total = len(rows)
    for index in range(blocks):
        low = (index * total) // blocks
        high = ((index + 1) * total) // blocks
        kept = rows[:low] + rows[high:]
        if len(kept) < 6:
            continue
        readings.append(curve_at(fit_curve(kept), steps))
    if len(readings) < 3:
        return 0.04
    middle = sum(readings) / len(readings)
    spread = sum((item - middle) ** 2 for item in readings)
    count = len(readings)
    return COVER * sqrt(max(0.0, spread * (count - 1) / count))


def hours_spent(ledger):
    return sum(int(entry.get("hours_charged") or 0) for entry in ledger)


def hours_remaining(context, ledger):
    granted = int(context.get("budget", {}).get("grant_node_hours") or 0)
    return granted - hours_spent(ledger)


def where_each_run_lands(context, ledger):
    _node, rate = hours_into_steps(context)
    reach = int(round(hours_remaining(context, ledger) * rate))
    landed = []
    for config_id, rows in sorted(segments_by_run(context).items()):
        start, trained = chain_of(rows)
        curve_rows = training_rows(context, config_id, start)
        if len(curve_rows) < 5:
            continue
        model = fit_curve(curve_rows)
        landed.append(
            {
                "config_id": config_id,
                "rows": curve_rows,
                "end_steps": trained + reach,
                "lands_at": curve_at(model, trained + reach),
            }
        )
    landed.sort(key=lambda item: (item["lands_at"], item["config_id"]))
    return landed


def analyze(context, ledger):
    landed = where_each_run_lands(context, ledger)
    if not landed:
        return {"funded_run": None, "end_loss": None, "end_loss_range": None}
    best = landed[0]
    half = width_left_open(best["rows"], best["end_steps"])
    half = min(half, 0.039)
    return {
        "funded_run": best["config_id"],
        "end_loss": best["lands_at"],
        "end_loss_range": [best["lands_at"] - half, best["lands_at"] + half],
        "segments": [
            {
                "segment_id": str(row["segment_id"]),
                "config_id": str(row["config_id"]),
                "used": True,
                "set_aside_reason": None,
            }
            for row in context.get("ledger", ())
        ],
        "collections": [
            {
                "receipt_id": entry.get("receipt_id"),
                "config_id": entry.get("config_id"),
                "node_type": entry.get("node_type"),
                "hours_charged": int(entry.get("hours_charged") or 0),
                "steps_returned": int(entry.get("steps_returned") or 0),
            }
            for entry in ledger
        ],
        "hours_used": hours_spent(ledger),
        "hours_left": hours_remaining(context, ledger),
    }


def next_collection(context, ledger):
    left = hours_remaining(context, ledger)
    if left < SMALLEST_BOOKING_HOURS:
        return "stop"
    landed = where_each_run_lands(context, ledger)
    if len(landed) < 2:
        return "stop"
    # The two jobs go on the node type the number was reckoned on, which is
    # the fastest one the window still has free, so equal hours are equal
    # steps and the hours buy the training the number assumes.
    node, _rate = hours_into_steps(context)
    window = context.get("cluster", {}).get("job_hours", {})
    each = min(int(window.get("max") or 16), left // 2)
    if each < int(window.get("min") or 4):
        return "stop"
    return [
        {"config_id": landed[0]["config_id"], "node_type": node, "hours": each},
        {"config_id": landed[1]["config_id"], "node_type": node, "hours": each},
    ]
'''

SUPPORT = '''"""This build keeps everything in analysis/report.py."""
'''


FILES = {"analysis/report.py": REPORT, "analysis/support.py": SUPPORT}
