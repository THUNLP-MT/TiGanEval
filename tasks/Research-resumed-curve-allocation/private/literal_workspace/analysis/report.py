"""Where the run at the top of the board lands once the rest of the window
goes to it.

The board's last-loss column says which run is ahead. This fits a power law to
that run's curve, reads it out at the steps the hours left buy at the pace that
run has been going, prints the fit's own scatter either side of it, and sends
the rest of the window to that run on the node it has been going out on.
"""

from math import exp, log, sqrt


def board_leader(context):
    """The run whose last logged row is the lowest, and that row."""

    best = None
    for config_id, rows in sorted(context.get("curves", {}).items()):
        if not rows:
            continue
        last = rows[-1]
        if best is None or float(last["loss"]) < best[1]:
            best = (config_id, float(last["loss"]), int(last["step"]), str(last["segment_id"]))
    return best


def own_rate(context, config_id):
    """How far this run has got per booked hour, over its own segments."""

    steps = hours = 0.0
    for row in context.get("ledger", ()):
        if str(row.get("config_id")) != str(config_id):
            continue
        steps += float(row.get("last_step") or 0.0)
        hours += float(row.get("wall_hours") or 0.0)
    return steps / hours if hours > 0.0 else 1000.0


def home_node(context, config_id):
    """The node a run has been going out on."""

    counts = {}
    for row in context.get("ledger", ()):
        if str(row.get("config_id")) == str(config_id):
            name = str(row.get("node_type"))
            counts[name] = counts.get(name, 0) + 1
    if not counts:
        return "n-a"
    return max(sorted(counts), key=lambda key: counts[key])


def _fit_two(power, loss):
    count = len(loss)
    s_t = s_tt = s_ty = s_y = 0.0
    for value, y in zip(power, loss):
        s_t += value
        s_tt += value * value
        s_ty += value * y
        s_y += y
    denominator = count * s_tt - s_t * s_t
    if abs(denominator) < 1e-12:
        return None
    amplitude = (count * s_ty - s_t * s_y) / denominator
    floor = (s_y - amplitude * s_t) / count
    residual = 0.0
    for value, y in zip(power, loss):
        gap = y - (floor + amplitude * value)
        residual += gap * gap
    return residual, floor, amplitude


def power_law(rows):
    """floor + amplitude * (step / 1000) ** -exponent over one stretch of curve."""

    logx = [log(max(1.0, step) / 1000.0) for step, _loss in rows]
    loss = [value for _step, value in rows]
    best = None
    for index in range(61):
        exponent = 0.15 + 0.55 * index / 60
        power = [exp(-exponent * value) for value in logx]
        got = _fit_two(power, loss)
        if got is not None and (best is None or got[0] < best[0]):
            best = (got[0], got[1], got[2], exponent)
    if best is None:
        return None
    residual, floor, amplitude, exponent = best
    spread = sqrt(residual / max(1, len(loss) - 3))
    return {"floor": floor, "amplitude": amplitude, "exponent": exponent, "spread": spread}


def read_out(model, steps):
    return model["floor"] + model["amplitude"] * (max(1.0, steps) / 1000.0) ** (
        -model["exponent"]
    )


def hours_left(context, ledger):
    granted = int(context.get("budget", {}).get("grant_node_hours") or 0)
    return granted - sum(int(entry.get("hours_charged") or 0) for entry in ledger)


def analyze(context, ledger):
    leader = board_leader(context)
    if leader is None:
        return {"funded_run": None, "end_loss": None, "end_loss_range": None}
    config_id, _last_loss, _last_step, segment_id = leader
    rows = [
        (int(row["step"]), float(row["loss"]))
        for row in context["curves"][config_id]
        if str(row["segment_id"]) == segment_id
    ]
    model = power_law(rows)
    reach = rows[-1][0] + hours_left(context, ledger) * own_rate(context, config_id)
    landing = read_out(model, reach)
    return {
        "funded_run": config_id,
        "end_loss": landing,
        "end_loss_range": [landing - model["spread"], landing + model["spread"]],
    }


def next_collection(context, ledger):
    """The rest of the window goes to the run at the top of the board."""

    leader = board_leader(context)
    config_id = leader[0] if leader else None
    return {
        "jobs": [
            {
                "config_id": config_id,
                "node_type": home_node(context, config_id),
                "hours": hours_left(context, ledger),
            }
        ]
    }
