"What the world says, computed from the world's own counts."

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping, Sequence

from . import world as w
from .world import VERSION_NEW, VERSION_OLD, Minute, World


TOLERANCE = Fraction(20, 10000)


def operations(world: World) -> int:
    return sum(minute.customer_operations for minute in world.minutes)


def failed_operations(world: World) -> int:
    return sum(minute.failed_operations for minute in world.minutes)


def truth(world: World) -> Fraction:
    'The share of customer operations that ended with no successful attempt.'

    return Fraction(failed_operations(world), operations(world))


def receipts_total(world: World) -> int:
    return sum(int(row["receipts"]) for row in world.rollup())


def error_receipts_total(world: World) -> int:
    return sum(int(row["receipts"]) for row in world.rollup() if row["outcome"] == "error")


def observed_operation_receipts(world: World) -> int:
    'First-attempt 2.4 receipts plus 2.3 receipts: operations with probes left in.'

    total = 0
    for minute in world.minutes:
        total += minute.operations[VERSION_OLD]
        total += minute.chain[VERSION_NEW][0][0] + minute.spilled
    return total


def observed_finals(world: World) -> int:
    'Receipts an operation-level reading counts as a failure, probes included.'

    return sum(
        minute.failed_operations + minute.expired for minute in world.minutes
    )


def _minute_finals(minute: Minute) -> int:
    return minute.first_attempt_finals()


def resolved(receipts: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], int]:
    '{(minute, pool): probes that expired there}, from the sealed receipts.'

    found: dict[tuple[str, str], int] = {}
    for entry in receipts:
        found[(str(entry["minute"]), str(entry["pool"]))] = int(
            entry["observed"]["probe_errors"]
        )
    return found


def probe_only(minute: Minute) -> bool:
    'Every 2.4 first attempt in this minute was a probe.'

    return minute.spilled > 0 and minute.chain[VERSION_NEW][0][0] == 0


def _known_and_open(world: World, receipts: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    'Expiries the export and the receipts pin down, and the clamp the rest leave.'

    seen = resolved(receipts)
    known = 0
    clamp = 0
    for minute in world.minutes:
        if probe_only(minute):
            known += minute.expired
            continue
        open_spilled = 0
        minute_known = 0
        for pool, (_emitted, spilled, _expired) in sorted(minute.pools.items()):
            if not spilled:
                continue
            if (minute.label, pool) in seen:
                minute_known += seen[(minute.label, pool)]
            else:
                open_spilled += spilled
        known += minute_known
        if open_spilled:
            clamp += min(open_spilled, max(0, _minute_finals(minute) - minute_known))
    return known, clamp


def feasible_range(world: World, receipts: Sequence[Mapping[str, Any]]) -> tuple[Fraction, Fraction]:
    'Every share the counters and the receipts still leave standing.'

    known, clamp = _known_and_open(world, receipts)
    total = Fraction(operations(world))
    high = Fraction(observed_finals(world) - known, 1) / total
    low = Fraction(observed_finals(world) - known - clamp, 1) / total
    return low, high


def window_range(world: World, receipts: Sequence[Mapping[str, Any]]) -> tuple[Fraction, Fraction]:
    'The range a reading that clamps once over the window would report.'

    seen = resolved(receipts)
    known = 0
    open_spilled = 0
    room = 0
    for minute in world.minutes:
        if probe_only(minute):
            known += minute.expired
            continue
        minute_known = 0
        for pool, (_emitted, spilled, _expired) in sorted(minute.pools.items()):
            if not spilled:
                continue
            if (minute.label, pool) in seen:
                minute_known += seen[(minute.label, pool)]
            else:
                open_spilled += spilled
        known += minute_known
        room += max(0, _minute_finals(minute) - minute_known)
    total = Fraction(operations(world))
    high = Fraction(observed_finals(world) - known, 1) / total
    clamp = min(open_spilled, room)
    low = Fraction(observed_finals(world) - known - clamp, 1) / total
    return low, high


def open_traces(world: World, receipts: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    'Retained, unpaid pool-minutes whose probe outcomes could still move the range.'

    seen = set(resolved(receipts))
    found = []
    for minute, pool in world.open_traces():
        if (minute, pool) not in seen:
            found.append((minute, pool))
    return found


def units_left(world: World, receipts: Sequence[Mapping[str, Any]]) -> int:
    return int(world.spec["units_granted"]) - w.units_spent(receipts)


def allowed_traces(world: World, receipts: Sequence[Mapping[str, Any]]) -> Any:
    'The pool-minutes a next call may name, or `stop` when there is nothing left.'

    if units_left(world, receipts) < int(world.spec["unit_cost"]):
        return "stop"
    left = open_traces(world, receipts)
    return set(left) if left else "stop"


def attempt_rate(world: World) -> Fraction:
    'Error receipts over all receipts: the share the dashboard draws.'

    return Fraction(error_receipts_total(world), receipts_total(world))


def probe_retained_rate(world: World) -> Fraction:
    'Operations counted right, probes left in the log.'

    return Fraction(observed_finals(world), observed_operation_receipts(world))


def probe_removed_attempt_rate(world: World) -> Fraction:
    'Probes taken out, every remaining receipt still counted as an operation.'

    spilled = sum(minute.spilled for minute in world.minutes)
    expired = sum(minute.expired for minute in world.minutes)
    return Fraction(error_receipts_total(world) - expired, receipts_total(world) - spilled)


def _switch_days(world: World) -> list[str]:
    days = [str(entry["day"]) for entry in world.spec["releases"]]
    return sorted(dict.fromkeys(days))


def date_keyed_operations(world: World, switch_day: str, *, drop_probes: bool,
                          keep_old: bool) -> int:
    "Operations counted by the calendar instead of by the receipt's own version."

    total = 0
    for minute in world.minutes:
        if minute.day < switch_day:
            total += minute.operations[VERSION_OLD]
            total += sum(entry[0] for entry in minute.chain[VERSION_NEW])
            total += minute.spilled
            if drop_probes:
                total -= minute.spilled
        else:
            total += minute.chain[VERSION_NEW][0][0]
            if not drop_probes:
                total += minute.spilled
            if keep_old:
                total += minute.operations[VERSION_OLD]
    return total


def date_keyed_counts(world: World) -> list[int]:
    'Every count a reading keyed on the crossover evening plausibly lands on.'

    return [
        date_keyed_operations(world, day, drop_probes=drop, keep_old=keep)
        for day in _switch_days(world)
        for drop in (True, False)
        for keep in (True, False)
    ]


def all_receipt_operations(world: World) -> int:
    return receipts_total(world)


def exhaustion_ignored_failures(world: World) -> int:
    'Failures counted as the receipts marked final, leaving the exhausted ones out.'

    total = 0
    for minute in world.minutes:
        total += minute.failed[VERSION_OLD]
        total += sum(entry[2] for entry in minute.chain[VERSION_NEW])
        total += minute.expired
    return total


def reference(world: World, receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'The report this world supports, in the shape the export reads a notebook in.'

    low, high = feasible_range(world, receipts)
    return {
        "operations": operations(world),
        "failed_operations": failed_operations(world),
        "failure_rate": float(truth(world)),
        "failure_rate_range": [float(low), float(high)],
        "exact": {"rate": truth(world), "low": low, "high": high},
    }
