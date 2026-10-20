'The campaign on the desk, and the campaigns the same notebook is run on next.'

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping, Sequence

from . import ledger as ledger_module
from .world import AREAS, WINDOWS, build


def _profiles(shifts: Sequence[str], rows: Sequence[Sequence[str]]) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    for shift, row in zip(shifts, rows):
        if sum(Fraction(str(value)) for value in row) != 4:
            raise ValueError(f"window profile for {shift} does not come to four windows")
        table[shift] = {window: str(value) for window, value in zip(WINDOWS, row)}
    return table


def _bases(codes: Sequence[str], values: Sequence[int]) -> dict[str, str]:
    if len(codes) != len(values):
        raise ValueError("every zone needs a base")
    return {code: str(value) for code, value in zip(codes, values)}


def _spec(
    *,
    campaign: str,
    label: str,
    lead_in: str,
    shifts: Sequence[str],
    settled_shifts: int,
    zone_home: Mapping[str, str],
    zone_base: Mapping[str, str],
    early_area: str | None,
    moved_zone: str | None,
    moved_from: str | None,
    moved_to: str | None,
    transfer_index: int | None,
    levels: Sequence[str],
    profiles: Sequence[Sequence[str]],
    calendar: Sequence[str],
    calendar_spread: str,
    zone_spread: str,
    drops_per_van: int,
    spill_multiple: str,
    allowance_left: int,
    standing_margin: str,
    short_window: tuple[int, str, str, str] | None,
    network_spread: str = "0.035",
    van_cap: int = 40,
    minimum_booking: int = 120,
    desk_fee: int = 6,
    reservation_days: int = 14,
    tolerance_pct: str = "4",
) -> dict[str, Any]:
    shifts = tuple(shifts)
    return {
        "campaign": campaign,
        "label": label,
        "lead_in": lead_in,
        "shifts": shifts,
        "settled_shifts": int(settled_shifts),
        "zone_home": dict(zone_home),
        "zone_base": dict(zone_base),
        "early_area": early_area,
        "moved_zone": moved_zone,
        "moved_from": moved_from,
        "moved_to": moved_to,
        "transfer_index": transfer_index,
        "shift_level": {shift: str(value) for shift, value in zip(shifts, levels)},
        "window_profile": _profiles(shifts, profiles),
        "calendar_move": {shift: str(value) for shift, value in zip(shifts, calendar)},
        "calendar_spread": calendar_spread,
        "zone_spread": zone_spread,
        "network_spread": network_spread,
        "drops_per_van": int(drops_per_van),
        "spill_multiple": spill_multiple,
        "van_cap": int(van_cap),
        "minimum_booking": int(minimum_booking),
        "desk_fee": int(desk_fee),
        "reservation_days": int(reservation_days),
        "allowance_total": 0,
        "allowance_left_now": int(allowance_left),
        "standing_margin": standing_margin,
        "short_window": short_window,
        "tolerance_pct": tolerance_pct,
    }


_W38_SHIFTS = (
    "2026-09-07",
    "2026-09-08",
    "2026-09-09",
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-16",
    "2026-09-17",
    "2026-09-18",
)

_HARBOUR_ZONES = tuple(f"Z-{number}" for number in (*range(101, 118), *range(119, 123)))
_RIDGE_ZONES = ("Z-118", *(f"Z-{number}" for number in range(123, 139)))

_HARBOUR_BASE = (14, 22, 18, 19, 16, 20, 13, 18, 17, 19, 21, 15, 23, 12, 18, 18, 20, 14, 22, 17, 19)
_RIDGE_BASE = (25, 16, 13, 18, 11, 15, 17, 12, 14, 16, 10, 17, 13, 15, 11, 18, 19)

W38 = _spec(
    campaign="dispatch-w38",
    label="the week 38 desk",
    lead_in="2026-09-04",
    shifts=_W38_SHIFTS,
    settled_shifts=5,
    zone_home={
        **{zone: "Harbour" for zone in _HARBOUR_ZONES},
        **{zone: "Ridge" for zone in _RIDGE_ZONES},
    },
    zone_base={**_bases(_HARBOUR_ZONES, _HARBOUR_BASE), **_bases(_RIDGE_ZONES, _RIDGE_BASE)},
    early_area="Ridge",
    moved_zone="Z-118",
    moved_from="Ridge",
    moved_to="Harbour",
    transfer_index=2,
    levels=("0.92", "1.14", "0.97", "1.21", "1.02", "0.88", "1.24", "0.90", "1.26", "0.92"),
    profiles=(
        ("1.06", "1.02", "0.97", "0.95"),
        ("0.94", "1.03", "1.08", "0.95"),
        ("1.10", "0.99", "0.95", "0.96"),
        ("0.96", "1.07", "1.02", "0.95"),
        ("1.04", "0.96", "1.05", "0.95"),
        ("1.05", "1.02", "0.98", "0.95"),
        ("1.03", "1.04", "0.98", "0.95"),
        ("1.06", "1.01", "0.98", "0.95"),
        ("1.02", "1.05", "0.98", "0.95"),
        ("1.04", "1.03", "0.98", "0.95"),
    ),
    calendar=(
        "-0.080", "0.024", "-0.038", "0.106", "-0.014",
        "0.043", "-0.061", "0.088", "-0.030", "0.019",
    ),
    calendar_spread="0.0704",
    zone_spread="0.09",
    drops_per_van=16,
    spill_multiple="11",
    allowance_left=520,
    standing_margin="1.18",
    short_window=(3, "Harbour", "W3", "0.92"),
)


_W41_HARBOUR = tuple(f"K-{number}" for number in (*range(201, 219), *range(220, 223)))
_W41_RIDGE = ("K-219", *(f"K-{number}" for number in range(223, 239)))

W41 = _spec(
    campaign="dispatch-w41",
    label="the week 41 desk",
    lead_in="2026-09-25",
    shifts=(
        "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02",
        "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
    ),
    settled_shifts=5,
    zone_home={
        **{zone: "Harbour" for zone in _W41_HARBOUR},
        **{zone: "Ridge" for zone in _W41_RIDGE},
    },
    zone_base={
        **_bases(
            _W41_HARBOUR,
            (17, 13, 21, 15, 19, 12, 24, 16, 14, 20, 18, 11, 22, 15, 17, 13, 19, 16, 21, 14, 18),
        ),
        **_bases(
            _W41_RIDGE,
            (22, 14, 11, 17, 13, 16, 10, 19, 12, 15, 18, 11, 14, 16, 12, 17, 13),
        ),
    },
    early_area="Harbour",
    moved_zone="K-219",
    moved_from="Ridge",
    moved_to="Harbour",
    transfer_index=3,
    levels=("1.06", "0.91", "1.19", "0.96", "1.13", "0.94", "1.22", "0.90", "1.24", "0.94"),
    profiles=(
        ("0.98", "1.05", "1.02", "0.95"),
        ("1.09", "0.99", "0.97", "0.95"),
        ("0.95", "1.03", "1.07", "0.95"),
        ("1.07", "1.00", "0.98", "0.95"),
        ("0.96", "1.08", "1.01", "0.95"),
        ("1.02", "1.04", "0.99", "0.95"),
        ("1.04", "1.02", "0.99", "0.95"),
        ("1.01", "1.05", "0.99", "0.95"),
        ("1.05", "1.01", "0.99", "0.95"),
        ("1.03", "1.03", "0.99", "0.95"),
    ),
    calendar=(
        "-0.062", "0.019", "-0.030", "0.083", "-0.011",
        "0.034", "-0.048", "0.069", "-0.024", "0.015",
    ),
    calendar_spread="0.0553",
    zone_spread="0.075",
    drops_per_van=18,
    spill_multiple="9",
    allowance_left=610,
    standing_margin="1.16",
    short_window=(4, "Ridge", "W2", "0.94"),
)

_W44_HARBOUR = tuple(f"N-{number}" for number in (*range(301, 320), *range(321, 324)))
_W44_RIDGE = ("N-320", *(f"N-{number}" for number in range(324, 340)))

W44 = _spec(
    campaign="dispatch-w44",
    label="the week 44 desk",
    lead_in="2026-10-16",
    shifts=(
        "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23",
        "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30",
    ),
    settled_shifts=5,
    zone_home={
        **{zone: "Harbour" for zone in _W44_HARBOUR},
        **{zone: "Ridge" for zone in _W44_RIDGE},
    },
    zone_base={
        **_bases(
            _W44_HARBOUR,
            (
                16, 19, 12, 22, 15, 18, 14, 20, 13, 17, 21, 12, 19, 15, 18, 11, 23, 16, 14,
                20, 17, 13,
            ),
        ),
        **_bases(
            _W44_RIDGE,
            (28, 15, 12, 19, 14, 11, 17, 13, 16, 10, 18, 12, 15, 11, 17, 14, 16),
        ),
    },
    early_area="Ridge",
    moved_zone="N-320",
    moved_from="Ridge",
    moved_to="Harbour",
    transfer_index=1,
    levels=("1.15", "0.93", "1.08", "1.22", "0.95", "0.90", "1.23", "0.92", "1.25", "0.91"),
    profiles=(
        ("1.02", "1.04", "0.99", "0.95"),
        ("0.96", "1.10", "0.99", "0.95"),
        ("1.08", "0.98", "0.99", "0.95"),
        ("0.97", "1.01", "1.07", "0.95"),
        ("1.05", "1.03", "0.97", "0.95"),
        ("1.04", "1.03", "0.98", "0.95"),
        ("1.02", "1.05", "0.98", "0.95"),
        ("1.06", "1.01", "0.98", "0.95"),
        ("1.03", "1.04", "0.98", "0.95"),
        ("1.05", "1.02", "0.98", "0.95"),
    ),
    calendar=(
        "-0.097", "0.029", "-0.046", "0.128", "-0.017",
        "0.052", "-0.074", "0.106", "-0.036", "0.023",
    ),
    calendar_spread="0.0851",
    zone_spread="0.105",
    drops_per_van=15,
    spill_multiple="13",
    allowance_left=480,
    standing_margin="1.10",
    short_window=(2, "Harbour", "W1", "0.90"),
)


_PILOT_HARBOUR = tuple(f"P-{number}" for number in range(401, 421))
_PILOT_RIDGE = tuple(f"P-{number}" for number in range(421, 437))

PILOT = _spec(
    campaign="dispatch-pilot",
    label="the pilot desk",
    lead_in="2026-11-06",
    shifts=(
        "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13",
        "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20",
    ),
    settled_shifts=5,
    zone_home={
        **{zone: "Harbour" for zone in _PILOT_HARBOUR},
        **{zone: "Ridge" for zone in _PILOT_RIDGE},
    },
    zone_base={
        **_bases(
            _PILOT_HARBOUR,
            (18, 15, 21, 13, 19, 16, 22, 14, 17, 20, 12, 18, 15, 23, 16, 19, 13, 21, 17, 14),
        ),
        **_bases(
            _PILOT_RIDGE,
            (17, 13, 19, 11, 16, 14, 18, 12, 15, 17, 13, 16, 11, 18, 14, 15),
        ),
    },
    early_area=None,
    moved_zone=None,
    moved_from=None,
    moved_to=None,
    transfer_index=None,
    levels=("0.90", "1.22", "0.95", "1.24", "0.98", "1.02", "0.93", "1.21", "0.96", "1.12"),
    profiles=(
        ("1.03", "1.01", "1.01", "0.95"),
        ("0.99", "1.04", "1.02", "0.95"),
        ("1.06", "1.00", "0.99", "0.95"),
        ("0.98", "1.05", "1.02", "0.95"),
        ("1.02", "1.02", "1.01", "0.95"),
        ("0.75", "1.50", "0.85", "0.90"),
        ("1.01", "1.03", "1.01", "0.95"),
        ("0.97", "1.06", "1.02", "0.95"),
        ("1.05", "0.99", "1.01", "0.95"),
        ("1.00", "1.04", "1.01", "0.95"),
    ),
    calendar=(
        "-0.114", "0.034", "-0.054", "0.150", "-0.020",
        "0.061", "-0.086", "0.124", "-0.042", "0.027",
    ),
    calendar_spread="0.1001",
    zone_spread="0.088",
    drops_per_van=17,
    spill_multiple="10",
    allowance_left=700,
    standing_margin="1.24",
    short_window=None,
)


def standing_booking(world: Any, shift: str) -> dict[tuple[str, str], int]:
    'The order the desk put on the road before this week, margin and all.'

    margin = Fraction(str(world.spec["standing_margin"]))
    short = world.spec.get("short_window")
    index = world.index_of(shift)
    booking: dict[tuple[str, str], int] = {}
    for area in AREAS:
        for window in WINDOWS:
            share = margin
            if short is not None and (index, area, window) == (short[0], short[1], short[2]):
                share = Fraction(str(short[3]))
            drops = world.demand(area, shift, window)
            booking[(area, window)] = world.vans_needed(int(drops * share))
    return booking


def settled_orders(world: Any) -> list[tuple[str, str, dict[tuple[str, str], int]]]:
    '(order id, shift, order) for the history, refusal included.'

    orders: list[tuple[str, str, dict[tuple[str, str], int]]] = []
    for index in range(world.settled_count):
        shift = world.shifts[index]
        tag = shift.replace("-", "")[4:]
        if index == 2:
            over = dict(standing_booking(world, shift))
            over[("Harbour", "W1")] = world.van_cap + 4
            orders.append((f"dw-{tag}a", shift, over))
            orders.append((f"dw-{tag}b", shift, standing_booking(world, shift)))
        else:
            orders.append((f"dw-{tag}", shift, standing_booking(world, shift)))
    return orders


def _priced(spec: Mapping[str, Any]) -> dict[str, Any]:
    'One spec with its allowance set so the history leaves what the desk holds.'

    provisional = dict(spec)
    provisional["allowance_total"] = 10**6
    world = build(provisional)
    entries = ledger_module.replay(world, settled_orders(world))
    spent = sum(float(entry["van_hours_charged"]) for entry in entries)
    settled = dict(spec)
    settled["allowance_total"] = int(round(spent)) + int(spec["allowance_left_now"])
    return settled


CURRENT = build(_priced(W38))
LATER = (build(_priced(W41)), build(_priced(W44)))
OUT_OF_REGIME = build(_priced(PILOT))
ALL_CAMPAIGNS = (CURRENT, *LATER, OUT_OF_REGIME)


def settled_stream(world: Any) -> list[dict[str, Any]]:
    "The receipts one campaign's history leaves on the ledger."

    return ledger_module.replay(world, settled_orders(world))


def campaign_of(name: str) -> Any:
    for world in ALL_CAMPAIGNS:
        if world.campaign == str(name):
            return world
    raise KeyError(name)
