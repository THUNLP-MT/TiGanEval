"What the world says, computed from the world's own parameters and counts."

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from . import world as w


TOLERANCE = 0.30


CLASSIFY_SLACK = 0.10


NARROW_FACTOR = 0.85
WIDE_FACTOR = 2.0


LOOK_RESPONSE_FRACTION = 0.8

COVERAGE = 0.9


CARRIED_OVER_GAP = 0.5


INVARIANCE_SLACK = 0.24

_NORMAL = NormalDist()


def lossy_fractions(world: w.World) -> dict[str, float]:
    "Per day, the share of that day's reorder events the topic never accepted."

    out: dict[str, float] = {}
    for row in world.ingestion_rows():
        offered = int(row["accepted"]) + int(row["dropped"])
        if row["dropped"] and offered:
            out[str(row["day"])] = int(row["dropped"]) / offered
    return out


def base_weights(world: w.World) -> dict[int, float]:
    'The share of the app base carrying each `sessions_28d` count.'

    counts = w.base_counts(world.spec)
    total = sum(counts.values())
    return {value: counts[value] / total for value in counts}


def cells(
    world: w.World,
    *,
    restore: bool = True,
    closed_only: bool = True,
) -> dict[tuple[str, int], tuple[int, float]]:
    '(arm, sessions_28d) -> users measured and the reorders they made.'

    close = world.closed_through()
    fractions = lossy_fractions(world)
    users: dict[tuple[str, int], int] = {}
    reorders: dict[tuple[str, int], float] = {}
    for (day, arm, value), count in world.enrolled.items():
        if closed_only and day > close:
            continue
        users[(arm, value)] = users.get((arm, value), 0) + count
    for (day, arm, value, published_on), count in world.published.items():
        if closed_only and day > close:
            continue
        scale = 1.0 / (1.0 - fractions.get(published_on, 0.0)) if restore else 1.0
        reorders[(arm, value)] = reorders.get((arm, value), 0.0) + count * scale
    return {key: (users[key], reorders.get(key, 0.0)) for key in users}


def _weighted(world: w.World, table: Mapping[tuple[str, int], tuple[int, float]]) -> float:
    weights = base_weights(world)
    total = 0.0
    for value, weight in sorted(weights.items()):
        treated = table.get(("treatment", value))
        control = table.get(("control", value))
        if not treated or not control or not treated[0] or not control[0]:
            continue
        total += weight * (treated[1] / treated[0] - control[1] / control[0])
    return total * 100.0


def _pooled(table: Mapping[tuple[str, int], tuple[int, float]]) -> float:
    arms = {arm: [0, 0.0] for arm in w.ARMS}
    for (arm, _value), (users, reorders) in table.items():
        arms[arm][0] += users
        arms[arm][1] += reorders
    if not arms["treatment"][0] or not arms["control"][0]:
        return 0.0
    return (
        arms["treatment"][1] / arms["treatment"][0]
        - arms["control"][1] / arms["control"][0]
    ) * 100.0


def truth(world: w.World) -> float:
    'The lift across the app base, in reorder points, as the world sets it.'

    return sum(
        float(world.spec["base_mix"][tier]) * float(world.spec["lift_points"][tier])
        for tier in w.TIERS
    )


def reading(world: w.World) -> float:
    "What the base's own weights give on this watch's published tables."

    return _weighted(world, cells(world))


def z_score(world: w.World) -> float:
    "Multiplier for the charter's one-sided false-ship bound over all looks."

    looks = max(1, int(world.spec["looks_granted"]))
    return _NORMAL.inv_cdf(1.0 - 0.05 / looks)


def half_width(world: w.World) -> float:
    'The bound the collected data supports, in reorder points.'

    table = cells(world)
    weights = base_weights(world)
    variance = 0.0
    for value, weight in sorted(weights.items()):
        treated = table.get(("treatment", value))
        control = table.get(("control", value))
        if not treated or not control or not treated[0] or not control[0]:
            continue
        rate_t = treated[1] / treated[0]
        rate_c = control[1] / control[0]
        variance += weight**2 * (
            rate_t * (1.0 - rate_t) / treated[0] + rate_c * (1.0 - rate_c) / control[0]
        )
    return z_score(world) * math.sqrt(variance) * 100.0


def interval(world: w.World) -> tuple[float, float]:
    value = reading(world)
    spread = half_width(world)
    return value - spread, value + spread


def decision(world: w.World) -> str:
    "Ship only when the bound the evidence supports clears the charter's line."

    low, _high = interval(world)
    return "ship" if low >= float(world.spec["ship_line_points"]) else "continue"


def closed_window_reading(world: w.World) -> float:
    "The lift among the users measured, with the base's own mix left out."

    return _pooled(cells(world))


def unrestored_reading(world: w.World) -> float:
    "The base's weights on a table the topic's shed events were never put back into."

    return _weighted(world, cells(world, restore=False))


def open_window_reading(world: w.World) -> float:
    'Reorders so far over everyone enrolled, windows closed or not.'

    return _weighted(world, cells(world, restore=False, closed_only=False))


def misreadings(world: w.World) -> dict[str, float]:
    return {
        "closed_window": closed_window_reading(world),
        "unrestored": unrestored_reading(world),
        "open_window": open_window_reading(world),
        "open_window_pooled": _pooled(cells(world, restore=False, closed_only=False)),
        "open_window_restored": _weighted(world, cells(world, closed_only=False)),
        "unrestored_closed_window": _pooled(cells(world, restore=False)),
    }


def safe_share(world: w.World) -> int:
    'The highest treated share the reorder topic can carry without shedding.'

    ceiling = int(world.spec["ceiling_events"])
    base = int(world.spec["base_events"])
    per_share = int(world.spec["per_share_events"])
    cap = int(world.spec["share_cap_pct"])
    share = cap
    while share > 1 and base + round(per_share * share / 100.0) > ceiling:
        share -= 1
    return share


def sheds_again(world: w.World, share_pct: int, days: int, hold_ramp: bool) -> bool:
    booking = {"share_pct": int(share_pct), "days": int(days), "hold_ramp": bool(hold_ramp)}
    ceiling = int(world.spec["ceiling_events"])
    base = int(world.spec["base_events"])
    per_share = int(world.spec["per_share_events"])
    return any(
        base + round(per_share * share / 100.0) > ceiling
        for share in w.booking_shares(world.spec, booking)
    )


def over_cap(world: w.World, share_pct: int, days: int, hold_ramp: bool) -> bool:
    booking = {"share_pct": int(share_pct), "days": int(days), "hold_ramp": bool(hold_ramp)}
    return max(w.booking_shares(world.spec, booking)) > int(world.spec["share_cap_pct"])


def booking_cost(world: w.World, share_pct: int, days: int, hold_ramp: bool) -> int:
    return w.booking_points(
        world.spec,
        {"share_pct": int(share_pct), "days": int(days), "hold_ramp": bool(hold_ramp)},
    )


_AFTER: dict[tuple[Any, ...], float] = {}


def half_width_after(
    world: w.World,
    bookings: Sequence[Mapping[str, Any]],
    share_pct: int,
    days: int,
    hold_ramp: bool,
) -> float:
    'The bound the watch would support after one more booking.'

    key = (
        world.watch,
        tuple(sorted((k, v) for item in bookings for k, v in item.items())),
        len(bookings),
        int(share_pct),
        int(days),
        bool(hold_ramp),
    )
    if key not in _AFTER:
        grown = w.booked(
            world.spec,
            [
                *bookings,
                {"share_pct": int(share_pct), "days": int(days), "hold_ramp": bool(hold_ramp)},
            ],
        )
        _AFTER[key] = half_width(grown)
    return _AFTER[key]


def informativeness_bar(world: w.World, bookings: Sequence[Mapping[str, Any]]) -> float:
    'A week of as much traffic as the topic will carry, and no more days.'

    return half_width_after(world, bookings, safe_share(world), 7, True)


def plan_state(world: w.World, bookings: Sequence[Mapping[str, Any]], points_left: int) -> dict[str, Any]:
    'What this watch can still book, and whether stopping is the only answer.'

    bar = informativeness_bar(world, bookings)
    left = int(points_left)
    reachable = left >= 1
    best = (
        half_width_after(world, bookings, 1, min(left, 60), True) if reachable else None
    )
    return {
        "points_left": left,
        "bar": bar,
        "safe_share": safe_share(world),
        "stop_only": not reachable or (best is not None and best > bar),
    }
