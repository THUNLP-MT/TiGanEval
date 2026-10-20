"What the world says, computed from the world's own parameters and rows."

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from . import world as w


TOLERANCE = 1.5


CLASSIFY_SLACK = 0.5


FAMILY_DAYS_SLACK = 0.035


NARROW_FACTOR = 0.9
WIDE_FACTOR = 1.5


ACCOUNT_DAYS_SLACK = 0.5

COVERAGE = 0.8


CARRIED_OVER_GAP = 0.6


INVARIANCE_SLACK = 0.8


NARROWING_EPSILON = 1e-9

COVER = 1.96

RISK_DAYS = 28


_PREPARED: dict[int, tuple[w.World, list[dict[str, Any]]]] = {}


def prepared(world: w.World) -> list[dict[str, Any]]:
    'Every flag with the things a reading of it turns on.'

    return list(world.derived)


def _walk(
    cells: dict[tuple[tuple[float, str], str], list[list[float]]],
    key: tuple[tuple[float, str], str],
    limit: int,
    escalated_on: int | None,
    horizon: int,
) -> None:
    at_risk, events = cells.setdefault(
        key, [[0.0] * (horizon + 1), [0.0] * (horizon + 1)]
    )
    for day in range(1, limit + 1):
        if escalated_on is not None and escalated_on < day:
            return
        at_risk[day] += 1.0
        if escalated_on == day:
            events[day] += 1.0
            return


def arm_cells(
    world: w.World, *, eligible_only: bool = True
) -> dict[tuple[tuple[float, str], str], list[list[float]]]:
    'Accounts at risk and escalations, per segment, side and day at risk.'

    cells: dict[tuple[tuple[float, str], str], list[list[float]]] = {}
    horizon = int(world.spec["risk_window_days"])
    window = int(world.spec["grace_window_days"])
    for row in prepared(world):
        if eligible_only and row["state"] != "active":
            continue
        watched = int(row["watched"])
        if watched < 1:
            continue
        if row["queue"] == "same_day":
            limit = min(horizon, watched)
            _walk(cells, (row["stratum"], "same_day"), limit, row["escalated_on"], horizon)
            continue
        started = row["waited"]
        reach = horizon if started is not None and started <= window else window
        limit = min(horizon, watched, reach)
        _walk(cells, (row["stratum"], "grace"), limit, row["escalated_on"], horizon)
    return cells


def naive_cells(world: w.World) -> dict[tuple[tuple[float, str], str], list[float]]:
    "The desk lead's own cut: the two groups her ledger filter makes."

    cells: dict[tuple[tuple[float, str], str], list[float]] = {}
    horizon = int(world.spec["risk_window_days"])
    window = int(world.spec["grace_window_days"])
    for row in prepared(world):
        started = row["waited"]
        if started is None:
            continue
        if started == 0:
            arm = "same_day"
        elif started <= window:
            arm = "grace"
        else:
            continue
        entry = cells.setdefault((row["stratum"], arm), [0.0, 0.0])
        entry[0] += 1.0
        escalated = row["escalated_on"]
        if escalated is not None and escalated <= horizon:
            entry[1] += 1.0
    return cells


def risk_of(counts: Sequence[Sequence[float]]) -> float:
    'The chance of an escalation over twenty-eight days on this side.'

    at_risk, events = counts
    days = sum(at_risk)
    if days <= 0:
        return 0.0
    rate = sum(events) / days
    return 1.0 - (1.0 - rate) ** RISK_DAYS


def variance_of(counts: Sequence[Sequence[float]]) -> float:
    'How far the chance above could sit from the one those days imply.'

    at_risk, events = counts
    days = sum(at_risk)
    if days <= 0:
        return 0.0
    rate = sum(events) / days
    if rate <= 0.0 or rate >= 1.0:
        return 0.0
    slope = RISK_DAYS * (1.0 - rate) ** (RISK_DAYS - 1)
    return slope * slope * rate * (1.0 - rate) / days


def book_weights(world: w.World) -> dict[tuple[float, str], float]:
    "The share of the desk's own book each segment carries."

    counts = {
        (float(error_rate), str(tier)): int(value)
        for (error_rate, tier), value in world.spec["book"].items()
    }
    total = sum(counts.values())
    return {key: counts[key] / total for key in counts}


def _combine(
    cells: Mapping[tuple[tuple[float, str], str], Any],
    weights: Mapping[tuple[float, str], float],
    read: Any,
) -> float:
    total = 0.0
    mass = 0.0
    for stratum, weight in sorted(weights.items()):
        held = cells.get((stratum, "grace"))
        same = cells.get((stratum, "same_day"))
        if held is None or same is None:
            continue
        total += weight * (read(held) - read(same))
        mass += weight
    return total / mass if mass else 0.0


def reading(world: w.World) -> float:
    "What the desk's own book weights give on the published tables."

    return _combine(arm_cells(world), book_weights(world), risk_of) * 100.0


def half_width(world: w.World) -> float:
    'The range the account-days behind the reading support, in points.'

    cells = arm_cells(world)
    weights = book_weights(world)
    total = 0.0
    mass = 0.0
    for stratum, weight in sorted(weights.items()):
        held = cells.get((stratum, "grace"))
        same = cells.get((stratum, "same_day"))
        if held is None or same is None:
            continue
        total += weight * weight * (variance_of(held) + variance_of(same))
        mass += weight
    if not mass:
        return 0.0
    return COVER * math.sqrt(total) / mass * 100.0


def account_days(world: w.World) -> float:
    cells = arm_cells(world)
    return float(sum(sum(counts[0]) for counts in cells.values()))


def most_account_days(world: w.World) -> float:
    "The most account-days this desk's rows could ever carry."

    return float(2 * int(world.spec["risk_window_days"]) * len(world.flags))


def supported_half_width(world: w.World, declared: Any) -> float:
    'The range the account-days a readout says it used would support.'

    base = half_width(world)
    held = account_days(world)
    if not isinstance(declared, (int, float)) or isinstance(declared, bool):
        return base
    used = min(float(declared), most_account_days(world))
    if used <= 0 or held <= 0:
        return base
    return base * math.sqrt(held / used)


def interval(world: w.World) -> tuple[float, float]:
    value = reading(world)
    spread = half_width(world)
    return value - spread, value + spread


_TRUTH: dict[int, tuple[w.World, float]] = {}


def _expected_mass(world: w.World) -> dict[tuple[Any, ...], float]:
    'Every kind of account the window raises, and how far it can be watched.'

    spec = world.spec
    flow = w.daily_flow(spec)
    horizon = int(spec["risk_window_days"])
    speaks = int(spec["migration_day"]) - int(spec["record_lag_days"])
    mass: dict[tuple[Any, ...], float] = {}
    for index in range(int(spec["window_days"])):
        week = index // 7
        load = w.week_load(spec, week)
        bar = w.bar_on(spec, index)
        waits = w.wait_weights_on(spec, week)
        wait_total = sum(waits.values())
        watched = max(0, min(horizon, speaks - index))
        if watched < 1:
            continue
        for error_rate in spec["error_values"]:
            for tier in spec["tiers"]:
                base = flow[(error_rate, tier)] * load
                same_day = float(
                    spec["same_day_share_above"]
                    if float(error_rate) >= bar
                    else spec["same_day_share_below"]
                )
                for state in w.STATES:
                    share = base * float(spec["state_shares"][state])
                    key = (error_rate, tier, state, "same_day", 0, watched)
                    mass[key] = mass.get(key, 0.0) + share * same_day
                    for wait, weight in waits.items():
                        if weight <= 0:
                            continue
                        key = (error_rate, tier, state, "next_slot", int(wait), watched)
                        mass[key] = mass.get(key, 0.0) + (
                            share * (1.0 - same_day) * weight / wait_total
                        )
    return mass


def truth(world: w.World) -> float:
    "What waiting costs at this desk, in points, from the world's own rates."

    held = _TRUTH.get(id(world))
    if held is not None and held[0] is world:
        return held[1]
    spec = world.spec
    horizon = int(spec["risk_window_days"])
    window = int(spec["grace_window_days"])
    cells: dict[tuple[tuple[float, str], str], list[list[float]]] = {}
    for (error_rate, tier, state, queue, wait, watched), amount in _expected_mass(world).items():
        if state != "active" or amount <= 0:
            continue
        arm = "same_day" if queue == "same_day" else "grace"
        reach = horizon if (queue == "same_day" or wait <= window) else window
        limit = min(horizon, watched, reach)
        path = w.hazard_path(spec, error_rate, tier, state, queue, wait)
        at_risk, events = cells.setdefault(
            ((float(error_rate), str(tier)), arm),
            [[0.0] * (horizon + 1), [0.0] * (horizon + 1)],
        )
        alive = 1.0
        for day in range(1, limit + 1):
            at_risk[day] += amount * alive
            events[day] += amount * alive * path[day - 1]
            alive *= 1.0 - path[day - 1]
    _TRUTH[id(world)] = (world, _combine(cells, book_weights(world), risk_of) * 100.0)
    return _TRUTH[id(world)][1]


def naive_reading(world: w.World) -> float:
    "Her cut, segment by segment and put back with the book's weights."

    return _combine(
        naive_cells(world), book_weights(world), lambda entry: entry[1] / entry[0]
    ) * 100.0


def naive_pooled_reading(world: w.World) -> float:
    'Her cut exactly as she took it: two groups, two proportions.'

    cells = naive_cells(world)
    arms = {"same_day": [0.0, 0.0], "grace": [0.0, 0.0]}
    for (_stratum, arm), entry in cells.items():
        arms[arm][0] += entry[0]
        arms[arm][1] += entry[1]
    if not arms["same_day"][0] or not arms["grace"][0]:
        return 0.0
    return (
        arms["grace"][1] / arms["grace"][0] - arms["same_day"][1] / arms["same_day"][0]
    ) * 100.0


def pooled_reading(world: w.World) -> float:
    "The clock read right and the desk's routing left out of it."

    cells = arm_cells(world)
    pooled: dict[tuple[tuple[float, str], str], list[list[float]]] = {}
    horizon = int(world.spec["risk_window_days"])
    for (_stratum, arm), counts in cells.items():
        entry = pooled.setdefault(
            ((0.0, "all"), arm), [[0.0] * (horizon + 1), [0.0] * (horizon + 1)]
        )
        for day in range(horizon + 1):
            entry[0][day] += counts[0][day]
            entry[1][day] += counts[1][day]
    return _combine(pooled, {(0.0, "all"): 1.0}, risk_of) * 100.0


def unstartable_reading(world: w.World) -> float:
    'The clock and the routing read right over every flag on the export.'

    return _combine(
        arm_cells(world, eligible_only=False), book_weights(world), risk_of
    ) * 100.0


def campaign_weighted_reading(world: w.World) -> float:
    "The right segments put back with the campaign's own weights."

    cells = arm_cells(world)
    counts: dict[tuple[float, str], float] = {}
    for (stratum, _arm), entry in cells.items():
        counts[stratum] = counts.get(stratum, 0.0) + entry[0][1]
    total = sum(counts.values())
    weights = {key: value / total for key, value in counts.items()} if total else {}
    return _combine(cells, weights, risk_of) * 100.0


def open_window_cells(
    world: w.World,
) -> dict[tuple[tuple[float, str], str], list[list[float]]]:
    'The held side carried to twenty-eight days however late the slot came.'

    cells: dict[tuple[tuple[float, str], str], list[list[float]]] = {}
    horizon = int(world.spec["risk_window_days"])
    for row in prepared(world):
        if row["state"] != "active":
            continue
        watched = int(row["watched"])
        if watched < 1:
            continue
        arm = "same_day" if row["queue"] == "same_day" else "grace"
        _walk(cells, (row["stratum"], arm), min(horizon, watched),
              row["escalated_on"], horizon)
    return cells


def clock_from_start_cells(
    world: w.World,
) -> dict[tuple[tuple[float, str], str], list[list[float]]]:
    'Both sides counted from the day the engagement opened, not the flag.'

    cells: dict[tuple[tuple[float, str], str], list[list[float]]] = {}
    horizon = int(world.spec["risk_window_days"])
    for row in prepared(world):
        if row["state"] != "active" or row["waited"] is None:
            continue
        offset = int(row["waited"])
        watched = int(row["watched"]) - offset
        if watched < 1:
            continue
        escalated = row["escalated_on"]
        shifted = None if escalated is None else escalated - offset
        if shifted is not None and shifted < 1:
            continue
        arm = "same_day" if row["queue"] == "same_day" else "grace"
        _walk(cells, (row["stratum"], arm), min(horizon, watched), shifted, horizon)
    return cells


def open_window_reading(world: w.World) -> float:
    return _combine(open_window_cells(world), book_weights(world), risk_of) * 100.0


def clock_from_start_reading(world: w.World) -> float:
    return _combine(clock_from_start_cells(world), book_weights(world), risk_of) * 100.0


def _days_of(cells: Mapping[tuple[tuple[float, str], str], Sequence[Sequence[float]]]) -> float:
    return float(sum(sum(counts[0]) for counts in cells.values()))


_MISREAD_DAYS: dict[int, tuple[w.World, dict[str, float | None]]] = {}


def misreading_account_days(world: w.World) -> dict[str, float | None]:
    'The account-days each wrong method is worked out over, where it has any.'

    held = _MISREAD_DAYS.get(id(world))
    if held is not None and held[0] is world:
        return held[1]
    same = _days_of(arm_cells(world))
    values: dict[str, float | None] = {
        "naive": None,
        "naive_weighted": None,
        "pooled": same,
        "campaign_weighted": same,
        "unstartable": _days_of(arm_cells(world, eligible_only=False)),
        "open_window": _days_of(open_window_cells(world)),
        "clock_from_start": _days_of(clock_from_start_cells(world)),
    }
    _MISREAD_DAYS[id(world)] = (world, values)
    return values


_MISREAD: dict[int, tuple[w.World, dict[str, float]]] = {}


def misreadings(world: w.World) -> dict[str, float]:
    'Every reading a known wrong method gives on this desk, worked out once.'

    held = _MISREAD.get(id(world))
    if held is not None and held[0] is world:
        return held[1]
    values = {
        "naive": naive_pooled_reading(world),
        "naive_weighted": naive_reading(world),
        "pooled": pooled_reading(world),
        "campaign_weighted": campaign_weighted_reading(world),
        "unstartable": unstartable_reading(world),
        "open_window": open_window_reading(world),
        "clock_from_start": clock_from_start_reading(world),
    }
    _MISREAD[id(world)] = (world, values)
    return values


def call_of(choice: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "segment": str(choice.get("segment", "all")),
        "hold_share": float(choice.get("hold_share", 0.0)),
        "slots": int(choice.get("slots", 0)),
        "accepted": True,
    }


def week_rows(world: w.World, bookings: Sequence[Mapping[str, Any]], call: Mapping[str, Any]) -> int:
    before = w.booked(world, list(bookings))
    after = w.booked(world, [*bookings, call_of(call)])
    return len(after.flags) - len(before.flags)


_AFTER: dict[tuple[Any, ...], float] = {}


def half_width_after(
    world: w.World, bookings: Sequence[Mapping[str, Any]], call: Mapping[str, Any]
) -> float:
    'The range the desk would support after one more week.'

    made = call_of(call)
    key = (
        world.desk,
        tuple(
            (item["segment"], item["hold_share"], item["slots"], item.get("accepted", True))
            for item in bookings
        ),
        made["segment"],
        made["hold_share"],
        made["slots"],
    )
    if key not in _AFTER:
        _AFTER[key] = half_width(w.booked(world, [*bookings, made]))
    return _AFTER[key]


def full_week(world: w.World, slots_left: int) -> int:
    'As many slots as a week takes, or as many as the grant can still buy.'

    return int(min(int(world.spec["slots_per_week"]), max(1, int(slots_left))))


def owners_week(world: w.World, slots_left: int) -> dict[str, Any]:
    "The week the desk lead's own instinct buys, as the sheet would take it."

    return {
        "segment": "all",
        "hold_share": float(world.spec["hold_cap"]),
        "slots": full_week(world, slots_left),
    }


_BAR: dict[tuple[Any, ...], float] = {}


def informativeness_bar(
    world: w.World, bookings: Sequence[Mapping[str, Any]], slots_left: int
) -> float:
    "The range left by the desk lead's stated week."

    slots = full_week(world, slots_left)
    key = (
        world.desk,
        tuple(
            (item["segment"], item["hold_share"], item["slots"], item.get("accepted", True))
            for item in bookings
        ),
        slots,
    )
    if key not in _BAR:
        _BAR[key] = half_width_after(world, bookings, owners_week(world, slots_left))
    return _BAR[key]


def is_over_cap(world: w.World, call: Mapping[str, Any], slots_left: int) -> str:
    spec = world.spec
    made = call_of(call)
    if made["slots"] > int(spec["slots_per_week"]):
        return "slots"
    if made["hold_share"] > float(spec["hold_cap"]) + 1e-9:
        return "hold"
    if made["slots"] > int(slots_left):
        return "grant"
    return ""


def plan_state(
    world: w.World, bookings: Sequence[Mapping[str, Any]], slots_left: int
) -> dict[str, Any]:
    'What this desk can still book, and whether stopping is the only answer.'

    spec = world.spec
    smallest = int(spec["smallest_week_slots"])
    left = int(slots_left)
    return {
        "slots_left": left,
        "bar": informativeness_bar(world, bookings, left) if left >= smallest else None,
        "stop_only": left < smallest,
    }
