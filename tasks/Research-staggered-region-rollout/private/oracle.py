"What the world says, computed from the world's own parameters and counts."

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from . import receipts as r
from . import world as w


TOLERANCE = 0.5


CLASSIFY_SLACK = 0.10


NARROW_FACTOR = 0.80
WIDE_FACTOR = 1.10


CARRIED_OVER_GAP = 0.6


INVARIANCE_SLACK = 0.25


NETWORKS_REVIEWED = 4

_NORMAL = NormalDist()


def z_score() -> float:
    'The multiplier a range needs to hold on every network the file runs.'

    return _NORMAL.inv_cdf(1.0 - 0.05 / (2.0 * NETWORKS_REVIEWED))


def single_network_z() -> float:
    return _NORMAL.inv_cdf(0.975)


def sample_rate(network: w.Network, region: str, day: str) -> float:
    total, placed, _assigned = network.sampled[(region, day)]
    return placed / total if total else 0.0


def printed_rate(network: w.Network, region: str, day: str) -> float:
    orders, ontime = network.printed[(region, day)]
    return ontime / orders if orders else 0.0


def exposure_of(network: w.Network, region: str, *, keep_rollback: bool) -> tuple[str, ...]:
    if keep_rollback:
        return network.exposure_days(region)
    item = network.region(region)
    length = int(network.spec["exposure_days"])
    return tuple(
        day
        for day in (w.shift(str(item.live_from), step) for step in range(length))
        if day <= network.as_of
    )


def controls_of(
    network: w.Network, region: str, day: str, *, only_waiting: bool
) -> tuple[str, ...]:
    if only_waiting:
        return network.controls_for(region, day)
    item = network.region(region)
    return tuple(
        sorted(
            other.name
            for other in network.regions
            if other.name != region
            and other.band == item.band
            and not (other.disabled_on is not None and str(day) >= other.disabled_on)
        )
    )


_COEFFICIENTS: dict[tuple[int, bool, bool], dict[tuple[str, str], float]] = {}
_VARIANCE: dict[int, float] = {}
_AFTER: dict[tuple[int, str, str, int], float] = {}


def coefficients(
    network: w.Network,
    *,
    only_waiting: bool = True,
    keep_rollback: bool = True,
) -> dict[tuple[str, str], float]:
    "How much each metro-day's rate weighs in the network's reading."

    key = (id(network), bool(only_waiting), bool(keep_rollback))
    if key in _COEFFICIENTS:
        return _COEFFICIENTS[key]
    _COEFFICIENTS[key] = _coefficients(
        network, only_waiting=only_waiting, keep_rollback=keep_rollback
    )
    return _COEFFICIENTS[key]


def _coefficients(
    network: w.Network,
    *,
    only_waiting: bool,
    keep_rollback: bool,
) -> dict[tuple[str, str], float]:
    book = network.book_orders()
    measured = network.measured_regions()
    total = sum(book[name] for name in measured)
    coef: dict[tuple[str, str], float] = {}

    def add(key: tuple[str, str], value: float) -> None:
        coef[key] = coef.get(key, 0.0) + value

    for name in measured:
        weight = book[name] / total
        exposure = exposure_of(network, name, keep_rollback=keep_rollback)
        baseline = network.baseline_days(name)
        if not exposure or not baseline:
            continue
        span, back = len(exposure), len(baseline)
        for day in exposure:
            add((name, day), weight / span)
        for day in baseline:
            add((name, day), -weight / back)
        for day in exposure:
            others = controls_of(network, name, day, only_waiting=only_waiting)
            if not others:
                continue
            for other in others:
                add((other, day), -weight / (span * len(others)))
                for base_day in baseline:
                    add((other, base_day), weight / (span * len(others) * back))
    return coef


def reading_with(
    network: w.Network,
    *,
    printed: bool = False,
    only_waiting: bool = True,
    keep_rollback: bool = True,
) -> float:
    "The network's effect in on-time points under one set of choices."

    rate = printed_rate if printed else sample_rate
    coef = coefficients(network, only_waiting=only_waiting, keep_rollback=keep_rollback)
    return 100.0 * sum(value * rate(network, name, day) for (name, day), value in coef.items())


def truth(network: w.Network) -> float:
    'What batching did over the book, in on-time points, as the world set it.'

    book = network.book_orders()
    measured = network.measured_regions()
    total = sum(book[name] for name in measured)
    value = 0.0
    for name in measured:
        days = network.exposure_days(name)
        item = network.region(name)
        value += book[name] * sum(
            w.effect_on(network.spec, item, day) for day in days
        ) / len(days)
    return value / total


def reading(network: w.Network) -> float:
    return reading_with(network)


def region_days(network: w.Network) -> int:
    'The metro-days of batching the reading is built on.'

    return sum(len(network.exposure_days(name)) for name in network.measured_regions())


def sampled_orders(network: w.Network) -> int:
    'The sampled orders behind the reading, exposure and baseline together.'

    coef = coefficients(network)
    return sum(int(network.sampled[key][0]) for key in coef)


def variance(network: w.Network) -> float:
    'What the sampled orders leave open in the reading, as a variance.'

    if id(network) in _VARIANCE:
        return _VARIANCE[id(network)]
    _VARIANCE[id(network)] = _variance(network)
    return _VARIANCE[id(network)]


def _variance(network: w.Network) -> float:
    coef = coefficients(network)
    total = 0.0
    for key, value in coef.items():
        count, placed, _assigned = network.sampled[key]
        if not count:
            continue
        share = placed / count
        total += value * value * share * (1.0 - share) / count
    return total


def half_width(network: w.Network) -> float:
    'The range the sampled orders support, in on-time points.'

    return z_score() * math.sqrt(variance(network)) * 100.0


def interval(network: w.Network) -> tuple[float, float]:
    value = reading(network)
    spread = half_width(network)
    return value - spread, value + spread


def _week_key(day: str) -> str:
    return day[:7] + "-" + str((int(day[8:10]) - 1) // 7)


def two_way_fit(network: w.Network, *, printed: bool = True) -> float:
    "The programme's own reading: a metro term, a week term and a live term."

    rate = printed_rate if printed else sample_rate
    rows = []
    for item in network.regions:
        for day in network.days:
            rows.append(
                (
                    item.name,
                    _week_key(day),
                    rate(network, item.name, day),
                    1.0 if item.live_on(day) else 0.0,
                )
            )
    columns = [[row[2] for row in rows], [row[3] for row in rows]]
    for values in columns:
        for _ in range(400):
            moved = 0.0
            for index in (0, 1):
                totals: dict[str, list[float]] = {}
                for row, value in zip(rows, values):
                    entry = totals.setdefault(row[index], [0.0, 0])
                    entry[0] += value
                    entry[1] += 1
                for position, row in enumerate(rows):
                    total, count = totals[row[index]]
                    values[position] -= total / count
                    moved += abs(total / count)
            if moved < 1e-12:
                break
    denominator = sum(value * value for value in columns[1])
    return 100.0 * sum(a * b for a, b in zip(columns[0], columns[1])) / denominator


_MISREAD: dict[int, dict[str, float]] = {}


def misreadings(network: w.Network) -> dict[str, float]:
    'The readings the three decisions of this project produce when made wrong.'

    if id(network) in _MISREAD:
        return _MISREAD[id(network)]
    _MISREAD[id(network)] = {
        "printed": reading_with(network, printed=True),
        "printed_live": reading_with(network, printed=True, only_waiting=False),
        "printed_rollback": reading_with(network, printed=True, keep_rollback=False),
        "printed_live_rollback": reading_with(
            network, printed=True, only_waiting=False, keep_rollback=False
        ),
        "live_controls": reading_with(network, only_waiting=False),
        "live_controls_rollback": reading_with(
            network, only_waiting=False, keep_rollback=False
        ),
        "rollback": reading_with(network, keep_rollback=False),
        "two_way_fit": two_way_fit(network),
        "two_way_fit_sampled": two_way_fit(network, printed=False),
    }
    return _MISREAD[id(network)]


def eligible_regions(
    network: w.Network, week: str, ledger: Sequence[Mapping[str, Any]] = ()
) -> tuple[str, ...]:
    'The metros the wave board will serve a holdback week on in that week.'

    floor = int(network.spec["minimum_orders_per_day"])
    end = w.shift(str(week), 6)
    charged = {str(entry["receipt_id"]) for entry in ledger}
    return tuple(
        sorted(
            item.name
            for item in network.regions
            if int(item.orders_per_day) > floor
            and not (item.live_from is not None and str(item.live_from) <= end)
            and r.receipt_id(item.name, str(week)) not in charged
        )
    )


def open_weeks(network: w.Network, ledger: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    'The weeks the board has not already filled to its three-a-week limit.'

    cap = int(network.spec["region_weeks_per_week"])
    taken: dict[str, int] = {}
    for entry in ledger:
        taken[str(entry["week"])] = taken.get(str(entry["week"]), 0) + 1
    return tuple(
        week for week in network.spec["bookable_weeks"] if taken.get(str(week), 0) < cap
    )


def week_variance(network: w.Network, region: str, week: str, holdback_share: int) -> float | None:
    "What one booked holdback week would leave open in that metro's effect."

    rows = w.booked_week_rows(network, region, week, int(holdback_share))
    arms: dict[str, list[int]] = {arm: [0, 0] for arm in w.ARMS}
    for row in rows:
        entry = arms[str(row["arm"])]
        entry[0] += int(row["sampled_orders"])
        entry[1] += int(row["ontime_by_placed_at"])
    total = 0.0
    for count, ontime in arms.values():
        if count <= 0:
            return None
        share = ontime / count
        total += share * (1.0 - share) / count
    return total


def half_width_after(
    network: w.Network, region: str, week: str, holdback_share: int
) -> float:
    key = (id(network), str(region), str(week), int(holdback_share))
    if key not in _AFTER:
        _AFTER[key] = _half_width_after(network, region, week, int(holdback_share))
    return _AFTER[key]


def _half_width_after(
    network: w.Network, region: str, week: str, holdback_share: int
) -> float:
    'The range the next board would carry once that week is on the evidence.'

    book = network.book_orders()
    measured = network.measured_regions()
    total = sum(book[name] for name in measured)
    added = int(book.get(region, 0)) if region not in measured else 0
    inner = week_variance(network, region, week, int(holdback_share))
    if not added or inner is None:
        return half_width(network)
    scale = total / (total + added)
    share = added / (total + added)
    grown = scale * scale * variance(network) + share * share * inner
    return z_score() * math.sqrt(grown) * 100.0


def owner_week(
    network: w.Network, ledger: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    "The programme manager's own next week: the largest metro left, least held back."

    weeks = open_weeks(network, ledger)
    if not weeks or r.weeks_left(network, ledger) < 1:
        return None
    week = weeks[0]
    names = [
        name
        for name in eligible_regions(network, week, ledger)
        if not r.refusal_for(network, ledger, name, week, int(network.spec["holdback_share_band"][0]))
    ]
    if not names:
        return None
    largest = max(names, key=lambda name: (network.region(name).orders_per_day, name))
    return {
        "region": largest,
        "week": week,
        "holdback_share": int(network.spec["holdback_share_band"][0]),
    }


def owner_bar(network: w.Network, ledger: Sequence[Mapping[str, Any]]) -> float | None:
    week = owner_week(network, ledger)
    if week is None:
        return None
    return half_width_after(
        network, str(week["region"]), str(week["week"]), int(week["holdback_share"])
    )


def best_week(
    network: w.Network, ledger: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any] | None, float | None]:
    'The week the book gains most from, and the range it would leave.'

    high = int(network.spec["holdback_share_band"][1])
    book = network.book_orders()
    best: tuple[dict[str, Any] | None, float | None] = (None, None)
    for week in open_weeks(network, ledger):
        for region in eligible_regions(network, week, ledger):
            if r.refusal_for(network, ledger, region, week, high):
                continue
            width = half_width_after(network, region, week, high)
            carried = int(book.get(region, 0))
            if best[1] is None or width < best[1]:
                best = (
                    {"region": region, "week": week, "holdback_share": high,
                     "book_orders": carried},
                    width,
                )
    return best


def plan_state(
    network: w.Network, ledger: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    'What this campaign can still book, and whether stopping is the only answer.'

    bar = owner_bar(network, ledger)
    week, best = best_week(network, ledger)
    return {
        "region_weeks_left": r.weeks_left(network, ledger),
        "bar": bar,
        "best": best,
        "best_week": week,


        "owner_week": owner_week(network, ledger),
        "nothing_to_buy": bar is None or week is None,
    }
