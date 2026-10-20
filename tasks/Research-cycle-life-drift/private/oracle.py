"What the world says, computed from the world's parameters."

from __future__ import annotations

from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence

from . import world


DIFFERENCE_TOLERANCE = Fraction(10)


MISREADING_TOLERANCE = Fraction(10)


def lot_id_of(context: Mapping[str, Any]) -> str:
    campaign = str(context.get("campaign"))
    for lot_id, lot in world.LOTS.items():
        if lot["campaign"] == campaign:
            return lot_id
    raise KeyError(campaign)


def qualification_bay(lot_id: str) -> str:
    lot = world.LOTS[lot_id]
    wanted = float(lot["qualification_temperature_c"])
    for bay, entry in lot["rack"].items():
        if float(entry["setpoint_c"]) == wanted:
            return bay
    raise ValueError(f"{lot_id} has no bay at {wanted} C")


def _session_of(lot: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    cells = list(receipt["observed"]["cells"])
    return {
        "bay": world.bay_of_channel(lot, int(receipt["channels"][0])),
        "protocol": str(receipt["protocol"]),
        "cells": len(cells),
    }


def session_lives(lot_id: str, receipt: Mapping[str, Any]) -> dict[str, int]:
    'The cycle each cell of one session actually retires at.'

    lot = world.LOTS[lot_id]
    session = _session_of(lot, receipt)
    lives = world.cell_lives(lot, session)
    return {
        str(cell["cell_id"]): int(life)
        for cell, life in zip(receipt["observed"]["cells"], lives)
    }


def raw_session_lives(lot_id: str, receipt: Mapping[str, Any]) -> dict[str, int]:
    'What the export reads as a retirement when the firmware gain is left in.'

    lot = world.LOTS[lot_id]
    session = dict(_session_of(lot, receipt), firmware=str(receipt["firmware"]))
    cycles = world.raw_retirement_cycles(lot, session)
    return {
        str(cell["cell_id"]): int(cycle)
        for cell, cycle in zip(receipt["observed"]["cells"], cycles)
    }


def endpoints(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {str(receipt["session_id"]): session_lives(lot_id, receipt) for receipt in receipts}


def raw_endpoints(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {str(receipt["session_id"]): raw_session_lives(lot_id, receipt) for receipt in receipts}


def _mean(values: Iterable[int]) -> Fraction | None:
    items = list(values)
    if not items:
        return None
    return Fraction(sum(items), len(items))


def group_lives(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[int]]:
    'Cell lives gathered by the chamber the cells were in and the charge they took.'

    lot = world.LOTS[lot_id]
    groups: dict[tuple[str, str], list[int]] = {}
    for receipt in receipts:
        bay = world.bay_of_channel(lot, int(receipt["channels"][0]))
        key = (bay, str(receipt["protocol"]))
        groups.setdefault(key, []).extend(session_lives(lot_id, receipt).values())
    return groups


def arm_mean(lot_id: str, receipts: Sequence[Mapping[str, Any]], bay: str,
             protocol: str) -> Fraction | None:
    return _mean(group_lives(lot_id, receipts).get((bay, protocol), ()))


def identified(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> bool:
    bay = qualification_bay(lot_id)
    return all(arm_mean(lot_id, receipts, bay, protocol) is not None
               for protocol in world.PROTOCOLS)


def difference(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> Fraction | None:
    'The extra cycles the stepped charge gives at the temperature that matters.'

    bay = qualification_bay(lot_id)
    stepped = arm_mean(lot_id, receipts, bay, "stepped")
    standard = arm_mean(lot_id, receipts, bay, "standard")
    if stepped is None or standard is None:
        return None
    return stepped - standard


def truth(lot_id: str) -> Fraction:
    "The world's own difference at the qualification temperature."

    lot = world.LOTS[lot_id]
    bay = qualification_bay(lot_id)
    return Fraction(lot["lives"][bay]["stepped"] - lot["lives"][bay]["standard"])


def supported_range(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> tuple[Fraction, Fraction]:
    'Everything the held receipts and the lot certificate still leave open.'

    lot = world.LOTS[lot_id]
    low, high = (Fraction(value) for value in lot["lot_life_window_cycles"])
    bay = qualification_bay(lot_id)
    stepped = arm_mean(lot_id, receipts, bay, "stepped")
    standard = arm_mean(lot_id, receipts, bay, "standard")
    if stepped is not None and standard is not None:
        value = stepped - standard
        return value, value
    if stepped is not None:
        return stepped - high, stepped - low
    if standard is not None:
        return low - standard, high - standard
    return low - high, high - low


def allowed_decisions(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> list[str]:
    bar = Fraction(world.LOTS[lot_id]["switch_threshold_cycles"])
    low, high = supported_range(lot_id, receipts)
    allowed = []
    if low >= bar:
        allowed.append("switch")
    if high < bar:
        allowed.append("keep")
    return allowed


def missing_arms(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> list[str]:
    bay = qualification_bay(lot_id)
    return [protocol for protocol in world.PROTOCOLS
            if arm_mean(lot_id, receipts, bay, protocol) is None]


def hours_left(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> int:
    if receipts:
        return int(receipts[-1]["channel_hours_remaining_after"])
    return int(world.LOTS[lot_id]["channel_hours_remaining"])


def allowed_plans(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> list[Any]:
    'The smallest booking that would settle the question, or nothing to book.'

    lot = world.LOTS[lot_id]
    if allowed_decisions(lot_id, receipts):
        return ["stop"]
    missing = missing_arms(lot_id, receipts)
    if not missing:
        return ["stop"]
    bay = qualification_bay(lot_id)
    cells = world.FIXTURE
    cost = cells * int(lot["channel_hours_per_cell"])
    if cost > hours_left(lot_id, receipts) or cells > len(lot["rack"][bay]["channels"]):
        return ["stop"]
    return [{"bay": bay, "protocol": protocol, "cells": cells} for protocol in missing]


def pooled_difference(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> Fraction | None:
    'Every stepped cell against every standard cell, whatever chamber they sat in.'

    groups = group_lives(lot_id, receipts)
    by_protocol: dict[str, list[int]] = {}
    for (_bay, protocol), lives in groups.items():
        by_protocol.setdefault(protocol, []).extend(lives)
    stepped = _mean(by_protocol.get("stepped", ()))
    standard = _mean(by_protocol.get("standard", ()))
    if stepped is None or standard is None:
        return None
    return stepped - standard


def logged_difference(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> Fraction | None:
    "The comparison you get by believing the chamber's temperature trace."

    lot = world.LOTS[lot_id]
    wanted = float(lot["qualification_temperature_c"])
    by_protocol: dict[str, list[int]] = {}
    for receipt in receipts:
        if float(receipt["chamber_logged_c"]) != wanted:
            continue
        by_protocol.setdefault(str(receipt["protocol"]), []).extend(
            session_lives(lot_id, receipt).values())
    stepped = _mean(by_protocol.get("stepped", ()))
    standard = _mean(by_protocol.get("standard", ()))
    if stepped is None or standard is None:
        return None
    return stepped - standard


def other_bay_difference(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'Differences carried over from a chamber the build never runs at.'

    lot = world.LOTS[lot_id]
    bay = qualification_bay(lot_id)
    values = []
    for other in lot["rack"]:
        if other == bay:
            continue
        stepped = arm_mean(lot_id, receipts, other, "stepped")
        standard = arm_mean(lot_id, receipts, other, "standard")
        if stepped is not None and standard is not None:
            values.append(stepped - standard)
    return values


def raw_difference(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> Fraction | None:
    'The right chamber, read off an export nobody put back on one scale.'

    lot = world.LOTS[lot_id]
    bay = qualification_bay(lot_id)
    by_protocol: dict[str, list[int]] = {}
    for receipt in receipts:
        if world.bay_of_channel(lot, int(receipt["channels"][0])) != bay:
            continue
        by_protocol.setdefault(str(receipt["protocol"]), []).extend(
            raw_session_lives(lot_id, receipt).values())
    stepped = _mean(by_protocol.get("stepped", ()))
    standard = _mean(by_protocol.get("standard", ()))
    if stepped is None or standard is None:
        return None
    return stepped - standard


def other_chamber_differences(lot_id: str,
                              receipts: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'Readings that come from letting cells of another chamber into the average.'

    values = [pooled_difference(lot_id, receipts), *other_bay_difference(lot_id, receipts)]
    return [value for value in values if value is not None]


def chamber_trace_differences(lot_id: str,
                              receipts: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'Readings that come from believing the temperature written on the sheet.'

    value = logged_difference(lot_id, receipts)
    wanted = difference(lot_id, receipts)
    if value is None or value == wanted:
        return []
    return [value]


def uncorrected_differences(lot_id: str,
                            receipts: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'Readings from the right chamber that nobody put back on one scale.'

    value = raw_difference(lot_id, receipts)
    wanted = difference(lot_id, receipts)
    if value is None or value == wanted:
        return []
    return [value]


def decoy_differences(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'Every reading a wrong grouping or a wrong scale produces, in one list.'

    return [
        *chamber_trace_differences(lot_id, receipts),
        *uncorrected_differences(lot_id, receipts),
        *other_chamber_differences(lot_id, receipts),
    ]
