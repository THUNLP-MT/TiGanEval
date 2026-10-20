'What the campaign should buy next, and when it should stop.'

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping, Sequence

from . import desk, oracle, reading, world


SMALLEST_REQUEST = 20


def credits_left(fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]) -> int:
    return desk.credits_left(fleet, receipts)


def request_cost(fleet: world.Fleet, profile: str, condition: str, rows: int) -> int:
    return desk.row_cost(fleet, str(profile), str(condition)) * int(rows)


def deciding_profiles(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> tuple[str, str]:
    'The bays the top two bundles are judged at, off the rows a build holds.'

    order = oracle.measured_ranking(fleet, receipts)
    return order[0][2], order[1][2]


def _gap_spread(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], added: Mapping[str, int]
) -> float:
    'How far apart the top two could still be, on the rows a build would hold.'

    total = 0.0
    for _, points, profile, rows in oracle.measured_ranking(fleet, receipts)[:2]:
        held = rows + int(added.get(profile, 0))
        share = points / 100.0
        total += share * (1.0 - share) / max(1, held)
    return 100.0 * sqrt(total)


def narrowing(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    profile: str,
    rows: int,
) -> float:
    'How much closer the top two stand once those rows are annotated.'

    before = _gap_spread(fleet, receipts, {})
    after = _gap_spread(fleet, receipts, {str(profile): int(rows)})
    return before - after


def owner_narrowing(fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]) -> float:
    'What a full counter request buys, which is the plan to beat.'

    cap = int(desk.terms(fleet)["max_rows_per_request"])
    return narrowing(fleet, receipts, "counter", cap)


def cell_has_units(fleet: world.Fleet, profile: str, firmware: str, condition: str) -> bool:
    'Whether the register has units in that bay, on that firmware, that see it.'

    if str(condition) == reading.REFERENCE_CARD:
        return True
    position = reading.CONDITIONS.index(str(condition))
    return any(
        unit.duty_profile == str(profile)
        and unit.firmware == str(firmware)
        and unit.shares[position] > 0.0
        for unit in fleet.units
    )


def _candidates(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every request the desk would take that buys more than the counter plan.'

    settings = desk.terms(fleet)
    cap = int(settings["max_rows_per_request"])
    minimum = int(settings["min_rows_per_request"])
    left = credits_left(fleet, receipts)
    beat = owner_narrowing(fleet, receipts)
    found: list[dict[str, Any]] = []
    for profile in dict.fromkeys(deciding_profiles(fleet, receipts)):
        cost = int(settings["credit_cost_per_row"][profile])
        rows = min(cap, left // cost)
        if rows < minimum:
            continue
        if narrowing(fleet, receipts, profile, rows) <= beat:
            continue
        for firmware in (
            str(fleet.spec["raised_firmware"]),
            str(fleet.spec["earlier_firmware"]),
        ):
            shares = oracle.mixture(fleet, profile)
            for condition in sorted(reading.CONDITIONS, key=lambda item: -shares[item]):
                if cell_has_units(fleet, profile, firmware, condition):
                    found.append(
                        {
                            "duty_profile": profile,
                            "firmware": firmware,
                            "condition": condition,
                            "rows": rows,
                        }
                    )
    return found


def must_stop(fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]) -> bool:
    'True when nothing left to buy would move the decision.'

    order = oracle.measured_ranking(fleet, receipts)
    if order[1][1] - order[0][1] > oracle.honest_width(fleet, receipts, order[0][0]):
        return True
    return not _candidates(fleet, receipts)


def plan_is_allowed(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], choice: Any
) -> str | None:
    'None when the request is one the campaign can act on, else the incident.'

    settings = desk.terms(fleet)
    if choice == "stop":
        return None if must_stop(fleet, receipts) else "stopped_with_credits_left"
    if not isinstance(choice, Mapping):
        return "capture_is_not_a_request_or_a_stop"
    profile = choice.get("duty_profile")
    firmware = choice.get("firmware")
    condition = choice.get("condition")
    rows = choice.get("rows")
    if profile not in world.PROFILES or condition not in settings["conditions"]:
        return "capture_is_not_a_request_or_a_stop"
    if firmware not in (str(fleet.spec["raised_firmware"]), str(fleet.spec["earlier_firmware"])):
        return "capture_is_not_a_request_or_a_stop"
    if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
        return "capture_is_not_a_request_or_a_stop"
    if rows < int(settings["min_rows_per_request"]):
        return "capture_below_minimum"
    if rows > int(settings["max_rows_per_request"]):
        return "capture_over_cap"
    if request_cost(fleet, profile, condition, rows) > credits_left(fleet, receipts):
        return "capture_over_credits"
    if not cell_has_units(fleet, profile, firmware, condition):
        return "capture_names_an_empty_cell"
    if str(condition) == reading.REFERENCE_CARD:
        return "capture_repeats_counter"
    if narrowing(fleet, receipts, profile, rows) <= owner_narrowing(fleet, receipts):
        return "capture_repeats_counter"
    return None


def one_allowed_plan(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> Any:
    'A request this campaign can act on now, or a stop when nothing is left.'

    if must_stop(fleet, receipts):
        return "stop"
    found = _candidates(fleet, receipts)
    return found[0] if found else "stop"
