'What the sweep says, computed from the runs rather than from a report.'

from __future__ import annotations

from math import exp, log, sqrt
from typing import Any, Mapping, Sequence

from . import world


TOLERANCE = 0.04


DECOY_SLACK = 0.012


MOVE_TOLERANCE = 0.02


COVER = 1.96


RANGE_FLOOR = 0.65


RANGE_SLACK = 5.0


RANGE_SPACING_RATIO = 0.60

RANGE_CEILING = 0.08


STOP_BELOW_HOURS = 8


def reckoning_node(campaign: world.Campaign) -> str:
    'The fastest node type the window still has free.'

    free = campaign.free_nodes()
    return max(free, key=lambda name: campaign.node_steps_per_hour(name))


def horizon_steps(campaign: world.Campaign) -> int:
    return campaign.hours_left() * campaign.node_steps_per_hour(reckoning_node(campaign))


def end_level(campaign: world.Campaign, run: world.Run) -> float:
    return run.level_at(run.steps_so_far() + horizon_steps(campaign))


def ranking(campaign: world.Campaign) -> list[world.Run]:
    return sorted(campaign.runs, key=lambda run: (end_level(campaign, run), run.config_id))


def funded(campaign: world.Campaign) -> world.Run:
    return ranking(campaign)[0]


def contenders(campaign: world.Campaign) -> tuple[world.Run, world.Run]:
    order = ranking(campaign)
    return order[0], order[1]


def contender_ids(campaign: world.Campaign) -> set[str]:
    return {run.config_id for run in contenders(campaign)}


def last_row_reading(campaign: world.Campaign, run: world.Run) -> float:
    row = campaign.last_row(run)
    return float(row["loss"]) if row else 0.0


def reset_counter_readings(campaign: world.Campaign, run: world.Run) -> list[float]:
    "The landing places a curve fitted on the last segment's own counter gives."

    if len(run.segments) < 2:
        return []
    rows = [
        (row["step"], row["lr"] / world.LR_PEAK, row["loss"])
        for row in campaign.rows(run)
        if row["segment_id"] == run.segments[-1].segment_id
    ]
    if len(rows) < 4:
        return []
    last_step = run.segments[-1].last_step
    left = campaign.hours_left()
    readings = []
    for carried in (rows, [(step, 0.0, loss) for step, _rate, loss in rows]):
        model = _fit(carried)
        for name in campaign.spec["node_steps_per_hour"]:
            reach = last_step + left * campaign.node_steps_per_hour(name)
            readings.append(_level_of(model, reach))
    return readings


def booking_reach_readings(campaign: world.Campaign, run: world.Run) -> list[float]:
    "Where this run's own curve sits at the reaches one booking would buy."

    left = campaign.hours_left()
    if left <= 0:
        return []
    low, high = job_window(campaign)
    trained = run.steps_so_far()
    hours = {0, low, high, left // 2, min(high, left // 2), left}
    return [
        run.level_at(trained + count * campaign.node_steps_per_hour(name))
        for name in campaign.free_nodes()
        for count in sorted(hours)
        if 0 <= count <= left
    ]


def shorter_run_readings(campaign: world.Campaign, run: world.Run) -> list[float]:
    'Every number this run gives for a run shorter than the one being funded.'

    landing = end_level(campaign, run)
    return [
        reading
        for reading in (
            *reset_counter_readings(campaign, run),
            *booking_reach_readings(campaign, run),
        )
        if abs(reading - landing) > TOLERANCE
    ]


def steps_of(campaign: world.Campaign, run: world.Run) -> list[tuple[float, float, float]]:
    '(training so far, learning rate as a fraction of peak, loss) per row.'

    rows: list[tuple[float, float, float]] = []
    before = 0
    by_segment: dict[str, list[Mapping[str, Any]]] = {}
    for row in campaign.rows(run):
        by_segment.setdefault(str(row["segment_id"]), []).append(row)
    for segment in run.segments:
        for row in by_segment.get(segment.segment_id, ()):
            rows.append(
                (before + float(row["step"]), float(row["lr"]) / world.LR_PEAK, float(row["loss"]))
            )
        before += int(segment.last_step)
    return rows


def _solve(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float] | None:
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


def _linear(exponent: float, logx: Sequence[float], u: Sequence[float], y: Sequence[float]):
    powers = [exp(-exponent * value) for value in logx]
    count = len(y)
    s_t = s_tt = s_tu = s_ty = 0.0
    s_u = s_uu = s_uy = s_y = 0.0
    for power, rate, loss in zip(powers, u, y):
        s_t += power
        s_tt += power * power
        s_tu += power * rate
        s_ty += power * loss
        s_u += rate
        s_uu += rate * rate
        s_uy += rate * loss
        s_y += loss
    beta = _solve(
        [[count, s_t, s_u], [s_t, s_tt, s_tu], [s_u, s_tu, s_uu + 1e-9]],
        [s_y, s_ty, s_uy],
    )
    if beta is None:
        return None
    floor, amplitude, instrument = beta
    residual = 0.0
    for power, rate, loss in zip(powers, u, y):
        gap = loss - (floor + amplitude * power + instrument * rate)
        residual += gap * gap
    return residual, floor, amplitude, instrument


def _fit(rows: Sequence[tuple[float, float, float]]) -> dict[str, Any]:
    "Floor, amplitude, exponent and instrument for one run's rows."

    logx = [log(max(1e-6, step) / 1000.0) for step, _rate, _loss in rows]
    u = [rate for _step, rate, _loss in rows]
    y = [loss for _step, _rate, loss in rows]
    low, high, grid = 0.12, 0.70, 25
    best = None
    for index in range(grid + 1):
        exponent = low + (high - low) * index / grid
        got = _linear(exponent, logx, u, y)
        if got is not None and (best is None or got[0] < best[0]):
            best = (got[0], exponent)
    if best is None:
        return {"floor": 0.0, "amplitude": 0.0, "exponent": 0.3, "sse": 0.0, "n": len(rows),
                "logx": logx, "u": u}
    span = (high - low) / grid
    lower, upper = max(low, best[1] - span), min(high, best[1] + span)
    ratio = (sqrt(5.0) - 1.0) / 2.0
    left, right = upper - ratio * (upper - lower), lower + ratio * (upper - lower)
    f_left, f_right = _linear(left, logx, u, y), _linear(right, logx, u, y)
    for _ in range(18):
        if f_left[0] < f_right[0]:
            upper, right, f_right = right, left, f_left
            left = upper - ratio * (upper - lower)
            f_left = _linear(left, logx, u, y)
        else:
            lower, left, f_left = left, right, f_right
            right = lower + ratio * (upper - lower)
            f_right = _linear(right, logx, u, y)
    exponent = (lower + upper) / 2.0
    residual, floor, amplitude, instrument = _linear(exponent, logx, u, y)
    return {
        "floor": floor, "amplitude": amplitude, "exponent": exponent,
        "instrument": instrument, "sse": residual, "n": len(rows), "logx": logx, "u": u,
    }


def _level_of(model: Mapping[str, Any], steps: float) -> float:
    return float(model["floor"]) + float(model["amplitude"]) * (
        max(1e-6, steps) / 1000.0
    ) ** (-float(model["exponent"]))


def supported_half(campaign: world.Campaign, run: world.Run) -> float:
    'Half the tightest honest range the retained rows of one run leave open.'

    rows = steps_of(campaign, run)
    if len(rows) <= 6:
        return RANGE_CEILING
    model = _fit(rows)
    spread = model["sse"] / max(1, model["n"] - 4)
    amplitude, exponent = model["amplitude"], model["exponent"]
    columns = []
    for logx, rate in zip(model["logx"], model["u"]):
        power = exp(-exponent * logx)
        columns.append([1.0, power, rate, -amplitude * power * logx])
    normal = [[sum(row[i] * row[j] for row in columns) for j in range(4)] for i in range(4)]
    steps = run.steps_so_far() + horizon_steps(campaign)
    log_end = log(max(1e-6, steps) / 1000.0)
    power_end = exp(-exponent * log_end)
    gradient = [1.0, power_end, 0.0, -amplitude * power_end * log_end]
    solved = _solve(normal, gradient)
    if solved is None:
        return RANGE_CEILING
    variance = spread * sum(a * b for a, b in zip(gradient, solved))
    return COVER * sqrt(max(variance, 0.0))


def job_window(campaign: world.Campaign) -> tuple[int, int]:
    window = campaign.spec["job_hours"]
    return int(window["min"]), int(window["max"])


def booked_steps(campaign: world.Campaign, jobs: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    steps: dict[str, int] = {}
    for job in jobs:
        node = str(job.get("node_type"))
        hours = int(job.get("hours") or 0)
        config = str(job.get("config_id"))
        steps[config] = steps.get(config, 0) + hours * campaign.node_steps_per_hour(node)
    return steps


def plan_is_allowed(campaign: world.Campaign, answer: Any) -> str | None:
    'None when the window can act on this answer, else the incident.'

    left = campaign.hours_left()
    low, high = job_window(campaign)
    if isinstance(answer, str):
        if answer.strip().lower() != "stop":
            return "plan_is_not_a_booking_or_a_stop"
        return None if left < STOP_BELOW_HOURS else "stop_premature"
    if not isinstance(answer, list) or not answer:
        return "plan_is_not_a_booking_or_a_stop"
    total = 0
    for job in answer:
        if not isinstance(job, Mapping):
            return "plan_is_not_a_booking_or_a_stop"
        config, node, hours = job.get("config_id"), job.get("node_type"), job.get("hours")
        if not isinstance(config, str) or not isinstance(node, str):
            return "plan_is_not_a_booking_or_a_stop"
        if not isinstance(hours, int) or isinstance(hours, bool):
            return "plan_is_not_a_booking_or_a_stop"
        if campaign.run(config) is None:
            return "booking_names_a_run_the_window_does_not_carry"
        if node not in campaign.free_nodes():
            return "booking_uses_unavailable_node"
        if hours < low or hours > high:
            return "booking_outside_job_window"
        total += hours
    if total > left:
        return "booking_over_the_hours_left"
    expected_node = reckoning_node(campaign)
    if any(str(job.get("node_type")) != expected_node for job in answer):
        return "booking_not_on_reckoning_node"
    wanted = contender_ids(campaign)
    steps = booked_steps(campaign, answer)
    if set(steps) != wanted:
        return "booking_not_separating"
    first, second = (steps[name] for name in sorted(steps))
    if not first or not second:
        return "booking_not_separating"
    if first != second:
        return "booking_steps_not_matched"
    return None


def one_allowed_plan(campaign: world.Campaign) -> Any:
    'A booking this window can act on now, or a stop when nothing is left.'

    left = campaign.hours_left()
    low, high = job_window(campaign)
    if left < STOP_BELOW_HOURS:
        return "stop"
    each = min(high, left // 2)
    node = reckoning_node(campaign)
    return [
        {"config_id": run.config_id, "node_type": node, "hours": each}
        for run in contenders(campaign)
    ]
