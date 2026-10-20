"""Reading a sweep window: how much training each run has had, where its curve
sits once the hours left are on it, and what its own rows leave open."""

from math import exp, log, sqrt


#: The range the group reads under a number.
COVER = 3.0
#: Under this many hours the window cannot put a job on each of the two runs
#: that can still win, so there is nothing left to buy.
STOP_BELOW_HOURS = 8


# -- the ledger --------------------------------------------------------------


def ledger_rows(context):
    return [dict(row) for row in context.get("ledger", ())]


def node_speeds(context):
    """What each node type turned a wall hour into, read off the segments."""

    seen = {}
    for row in ledger_rows(context):
        hours = float(row.get("wall_hours") or 0.0)
        steps = float(row.get("last_step") or 0.0)
        if hours > 0.0 and steps > 0.0:
            seen.setdefault(str(row["node_type"]), []).append(steps / hours)
    return {name: sorted(values)[len(values) // 2] for name, values in seen.items()}


def open_node(context):
    """The fastest node type the window still has free, and what it turns an
    hour into."""

    reserved = set(context.get("cluster", {}).get("reserved_node_types", ()))
    speeds = node_speeds(context)
    free = {name: rate for name, rate in speeds.items() if name not in reserved}
    if not free:
        free = speeds
    name = max(free, key=lambda key: free[key])
    return name, free[name]


def chains(context):
    """Per run, its segments in the order they were run and where each starts.

    A segment that resumes another one writes its own step counter from zero,
    so the training a row stands at is the row's step plus every step the
    segments before it ran.
    """

    by_run = {}
    for row in ledger_rows(context):
        by_run.setdefault(str(row["config_id"]), []).append(row)
    ordered = {}
    for config_id, rows in by_run.items():
        after = {}
        first = None
        for row in rows:
            parent = row.get("resumed_from")
            if parent is None:
                first = row
            else:
                after[str(parent)] = row
        chain = []
        current = first if first is not None else rows[0]
        seen = set()
        while current is not None and str(current["segment_id"]) not in seen:
            seen.add(str(current["segment_id"]))
            chain.append(current)
            current = after.get(str(current["segment_id"]))
        for row in rows:
            if str(row["segment_id"]) not in seen:
                chain.append(row)
        offsets = {}
        before = 0
        for row in chain:
            offsets[str(row["segment_id"])] = before
            before += int(row["last_step"])
        ordered[config_id] = {"chain": chain, "offsets": offsets, "steps": before}
    return ordered


def curve_rows(context, config_id, offsets):
    """(training so far, learning rate over its peak, loss) for one run's rows."""

    rows = list(context.get("curves", {}).get(config_id, ()))
    peak = 0.0
    for row in rows:
        peak = max(peak, float(row.get("lr") or 0.0))
    peak = peak or 1.0
    out = []
    for row in rows:
        offset = offsets.get(str(row.get("segment_id")))
        if offset is None:
            continue
        out.append(
            (offset + float(row["step"]), float(row["lr"]) / peak, float(row["loss"]))
        )
    out.sort(key=lambda item: item[0])
    return out


# -- the curve one run is on -------------------------------------------------


def _solve(matrix, rhs):
    size = len(rhs)
    table = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(table[r][column]))
        if abs(table[pivot][column]) < 1e-14:
            return None
        table[column], table[pivot] = table[pivot], table[column]
        head = table[column]
        for row in range(size):
            if row == column:
                continue
            factor = table[row][column] / head[column]
            if factor:
                for cell in range(column, size + 1):
                    table[row][cell] -= factor * head[cell]
    return [table[index][size] / table[index][index] for index in range(size)]


def _linear(exponent, logx, rate, loss):
    powers = [exp(-exponent * value) for value in logx]
    count = len(loss)
    s_t = s_tt = s_tu = s_ty = 0.0
    s_u = s_uu = s_uy = s_y = 0.0
    for power, u, y in zip(powers, rate, loss):
        s_t += power
        s_tt += power * power
        s_tu += power * u
        s_ty += power * y
        s_u += u
        s_uu += u * u
        s_uy += u * y
        s_y += y
    beta = _solve(
        [[count, s_t, s_u], [s_t, s_tt, s_tu], [s_u, s_tu, s_uu + 1e-9]],
        [s_y, s_ty, s_uy],
    )
    if beta is None:
        return None
    floor, amplitude, instrument = beta
    residual = 0.0
    for power, u, y in zip(powers, rate, loss):
        gap = y - (floor + amplitude * power + instrument * u)
        residual += gap * gap
    return residual, floor, amplitude, instrument


_FITS = {}


def fit(rows):
    """A run's curve and the amount its rows carry from the schedule.

    A row is the run's level plus an amount that goes with the learning rate
    the row was written at, so the learning rate column is carried alongside
    the curve rather than left in the scatter.
    """

    key = (len(rows), rows[0] if rows else None, rows[-1] if rows else None)
    if key in _FITS:
        return _FITS[key]
    logx = [log(max(1e-6, step) / 1000.0) for step, _rate, _loss in rows]
    rate = [item for _step, item, _loss in rows]
    loss = [item for _step, _rate, item in rows]
    low, high, grid = 0.12, 0.70, 25
    best = None
    for index in range(grid + 1):
        exponent = low + (high - low) * index / grid
        got = _linear(exponent, logx, rate, loss)
        if got is not None and (best is None or got[0] < best[0]):
            best = (got[0], exponent)
    span = (high - low) / grid
    lower, upper = max(low, best[1] - span), min(high, best[1] + span)
    ratio = (sqrt(5.0) - 1.0) / 2.0
    left, right = upper - ratio * (upper - lower), lower + ratio * (upper - lower)
    f_left, f_right = _linear(left, logx, rate, loss), _linear(right, logx, rate, loss)
    for _ in range(18):
        if f_left[0] < f_right[0]:
            upper, right, f_right = right, left, f_left
            left = upper - ratio * (upper - lower)
            f_left = _linear(left, logx, rate, loss)
        else:
            lower, left, f_left = left, right, f_right
            right = lower + ratio * (upper - lower)
            f_right = _linear(right, logx, rate, loss)
    exponent = (lower + upper) / 2.0
    residual, floor, amplitude, instrument = _linear(exponent, logx, rate, loss)
    model = {
        "floor": floor, "amplitude": amplitude, "exponent": exponent,
        "instrument": instrument, "sse": residual, "n": len(rows),
        "logx": logx, "rate": rate,
    }
    _FITS[key] = model
    return model


def level_at(model, steps):
    """Where the fitted curve sits after this much training."""

    return model["floor"] + model["amplitude"] * (max(1e-6, steps) / 1000.0) ** (
        -model["exponent"]
    )


def half_width(model, steps, cover=COVER):
    """How far the number can still move on the rows behind the curve.

    The rows fix the curve only so far, and reading it out past where they
    stop widens what they leave open, so both the scatter about the curve and
    the reach of the number go into the width.
    """

    if model["n"] <= 6:
        return 0.04
    spread = model["sse"] / max(1, model["n"] - 4)
    amplitude, exponent = model["amplitude"], model["exponent"]
    columns = []
    for logx, rate in zip(model["logx"], model["rate"]):
        power = exp(-exponent * logx)
        columns.append([1.0, power, rate, -amplitude * power * logx])
    normal = [[sum(row[i] * row[j] for row in columns) for j in range(4)] for i in range(4)]
    log_end = log(max(1e-6, steps) / 1000.0)
    power_end = exp(-exponent * log_end)
    gradient = [1.0, power_end, 0.0, -amplitude * power_end * log_end]
    solved = _solve(normal, gradient)
    if solved is None:
        return 0.04
    variance = spread * sum(a * b for a, b in zip(gradient, solved))
    return cover * sqrt(max(variance, 0.0))


# -- where the hours land ----------------------------------------------------


def hours_used(ledger):
    return sum(int(entry.get("hours_charged") or 0) for entry in ledger)


def hours_left(context, ledger):
    granted = int(context.get("budget", {}).get("grant_node_hours") or 0)
    return granted - hours_used(ledger)


def landings(context, ledger):
    """Per run: the training it has had, and where its curve lands after the
    hours left are spent on it."""

    _node, rate = open_node(context)
    left = hours_left(context, ledger)
    reach = int(round(left * rate))
    found = []
    for config_id, entry in sorted(chains(context).items()):
        rows = curve_rows(context, config_id, entry["offsets"])
        if len(rows) < 5:
            continue
        model = fit(rows)
        end_steps = entry["steps"] + reach
        found.append(
            {
                "config_id": config_id,
                "steps_so_far": entry["steps"],
                "end_steps": end_steps,
                "end_loss": level_at(model, end_steps),
                "half_width": half_width(model, end_steps),
                "rows": len(rows),
            }
        )
    found.sort(key=lambda item: (item["end_loss"], item["config_id"]))
    return found


def segment_lines(context):
    return [
        {
            "segment_id": str(row["segment_id"]),
            "config_id": str(row["config_id"]),
            "used": True,
            "set_aside_reason": None,
        }
        for row in ledger_rows(context)
    ]


def collection_lines(ledger):
    return [
        {
            "receipt_id": entry.get("receipt_id"),
            "config_id": entry.get("config_id"),
            "node_type": entry.get("node_type"),
            "hours_charged": int(entry.get("hours_charged") or 0),
            "steps_returned": int(entry.get("steps_returned") or 0),
        }
        for entry in ledger
    ]
