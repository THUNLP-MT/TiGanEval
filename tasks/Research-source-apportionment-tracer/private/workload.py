"The window under study, the ones the same notebook is used on next, and the matching blocks the review reads a reading's stability off."

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .world import build, days_from, redrawn


SIGNATURES = {
    "conductivity": (688.0, 336.0, 452.0),
    "marker": (7.6, 6.9, 0.38),
    "ripple": (14.0, 33.0, 5.0),
}

SIGMA = {
    "conductivity_5": 6.0,
    "conductivity_30": 2.5,
    "marker_5": 0.12,
    "marker_30": 0.035,
    "ripple": 0.6,
}

ACCESS_POINTS = ("header", "tie_in_plant_room", "gas_plant_room", "east_riser")


CHANGEOVER_MIXTURE = (0.30, 0.70, 0.0)

LOAD = {"load_base_kw": 10.0, "load_per_C_kw": 110.0, "load_base_C": 15.5}


def _visit(day: str, point: str, times: Sequence[str], dwell_min: int = 5) -> dict[str, Any]:
    return {
        "day": day,
        "point": point,
        "at": [f"{day}T{stamp}:00" for stamp in times],
        "dwell_min": dwell_min,
    }


def _spec(
    lot: str,
    block: str,
    first_day: str,
    outdoor_C: Sequence[float],
    visits: Sequence[Mapping[str, Any]],
    operations: Sequence[Mapping[str, Any]],
    recovery_at_base: float,
    gas_at_base: float,
    mixture_base_C: float,
    sheet_read_on: str,
    sheet_outdoor_C: float,
    shift_per_C: float,
    sample_prefix: str,
    after_days: Sequence[tuple[str, float]],
    marker_signature: float | None = None,
    slots_granted: int = 30,
) -> dict[str, Any]:
    signatures = dict(SIGNATURES)
    if marker_signature is not None:
        marker = list(SIGNATURES["marker"])
        marker[2] = float(marker_signature)
        signatures["marker"] = tuple(marker)
    return {
        "lot": lot,
        "block": block,
        "first_day": first_day,
        "days": len(outdoor_C),
        "outdoor_C": [float(value) for value in outdoor_C],
        "visits": [dict(visit) for visit in visits],
        "operations": [dict(entry) for entry in operations],
        "recovery_at_base": float(recovery_at_base),
        "recovery_per_C": 0.0037,
        "gas_at_base": float(gas_at_base),
        "gas_per_C": 0.0115,
        "mixture_base_C": float(mixture_base_C),
        "signatures": signatures,
        "sigma": dict(SIGMA),
        "sheet_read_on": sheet_read_on,
        "sheet_outdoor_C": float(sheet_outdoor_C),
        "shift_per_C": float(shift_per_C),
        "marker_floor_5": 1.0,
        "marker_floor_30": 0.2,
        "sample_prefix": sample_prefix,
        "after_days": [(str(day), float(value)) for day, value in after_days],
        "slots_granted": int(slots_granted),
        "slots_per_visit": 4,
        "long_dwell_slots": 2,
        "module_slots": 2,
        "access_points": ACCESS_POINTS,
        "collection_days": [str(day) for day, _value in after_days],
        "share_within": 0.04,
        "band_ask": 0.02,
        **LOAD,
    }


JANUARY_OUTDOOR = (
    6.3, 5.8, 6.2, 7.2, 5.3, 4.2, 3.0, 0.6, -2.0, -4.4, -5.8, -6.0, -5.0, -2.7,
    -0.2, 1.6, 2.5, 4.0, 5.2, 6.2, 4.8, 3.5, 2.2, 1.3, 2.8, 5.0, 0.8, 0.6, 0.9,
    0.5, 0.7,
)

_CHANGEOVER = {
    "day": "2026-01-12",
    "from": "14:00",
    "to": "16:00",
    "entry": (
        "changeover on the plant-room set: east riser valved out and the tie-in "
        "interface set isolated; gas plant carrying the block"
    ),
    "held_mixture": CHANGEOVER_MIXTURE,
}

JANUARY_OPERATIONS = (
    {
        "day": "2026-01-08",
        "from": "09:00",
        "to": "11:30",
        "entry": "analyser off the header for its quarterly service; probe back on before noon",
    },
    _CHANGEOVER,
    {
        "day": "2026-01-22",
        "from": "06:00",
        "to": "18:00",
        "entry": "boiler-house lift out of service; contractor access by the north stair",
    },
)

JANUARY_VISITS = (
    _visit("2026-01-04", "header", ("09:15", "09:45", "10:15", "10:45")),
    _visit("2026-01-12", "header", ("09:20", "09:55", "14:20", "15:05")),
    _visit("2026-01-20", "header", ("09:10", "09:40", "10:10")),
    _visit("2026-01-26", "header", ("09:25", "10:00")),
)


JANUARY_AFTER = (
    ("2026-02-01", 0.9), ("2026-02-02", 0.4), ("2026-02-03", 1.1),
    ("2026-02-04", 0.6), ("2026-02-05", 1.3),
)

CURRENT_SPEC = _spec(
    lot="block-a-january",
    block="Block A",
    first_day="2026-01-01",
    outdoor_C=JANUARY_OUTDOOR,
    visits=JANUARY_VISITS,
    operations=JANUARY_OPERATIONS,
    recovery_at_base=0.190,
    gas_at_base=0.290,
    mixture_base_C=0.8,
    sheet_read_on="2026-01-04",
    sheet_outdoor_C=7.2,
    shift_per_C=6.2,
    sample_prefix="hs",
    after_days=JANUARY_AFTER,
)


HISTORY_VISITS = (
    {"call_id": "round-01", "point": "header", "samples": 4, "served_on": "2026-01-04"},
    {"call_id": "round-02", "point": "header", "samples": 4, "served_on": "2026-01-12"},
    {"call_id": "round-03", "point": "header", "samples": 3, "served_on": "2026-01-20"},
    {"call_id": "round-04", "point": "header", "samples": 2, "served_on": "2026-01-26"},
    {"call_id": "round-05", "point": "boiler_house", "samples": 3, "served_on": "2026-01-26"},
)


FEBRUARY_OUTDOOR = (
    3.7, 5.1, 6.4, 6.8, 5.6, 2.9, 0.8, -1.4, -3.4, -1.7, 1.3, 3.4, 4.9, 6.1,
    6.4, 5.7, 4.3, 2.6, 1.1, -0.3, -2.1, -0.6, 1.9, 3.5, 4.2, 2.7, 2.5, 2.8,
)

FEBRUARY_SPEC = _spec(
    lot="block-a-february",
    block="Block A",
    first_day="2026-02-01",
    outdoor_C=FEBRUARY_OUTDOOR,
    visits=(
        _visit("2026-02-04", "header", ("09:15", "09:45", "10:15")),
        _visit("2026-02-09", "header", ("09:20", "09:50", "13:40", "14:25")),
        _visit("2026-02-15", "header", ("09:10", "09:40", "10:10", "10:40")),
        _visit("2026-02-25", "header", ("09:25", "10:00", "10:35")),
    ),
    operations=(
        {
            "day": "2026-02-09",
            "from": "13:20",
            "to": "15:00",
            "entry": (
                "changeover on the plant-room set: east riser valved out and the tie-in "
                "interface set isolated; gas plant carrying the block"
            ),
            "held_mixture": CHANGEOVER_MIXTURE,
        },
        {
            "day": "2026-02-18",
            "from": "07:00",
            "to": "12:00",
            "entry": "roof plant washdown; no access to the header room before noon",
        },
    ),
    recovery_at_base=0.240,
    gas_at_base=0.245,
    mixture_base_C=2.088,
    sheet_read_on="2026-02-04",
    sheet_outdoor_C=6.8,
    shift_per_C=6.2,
    sample_prefix="fs",
    after_days=(("2026-03-01", 1.7), ("2026-03-02", 2.1), ("2026-03-03", 1.4)),
)

MARCH_OUTDOOR = (
    5.0, 6.1, 7.5, 7.4, 7.0, 5.2, 3.5, 1.8, -0.3, -1.9, -0.5, 1.6, 3.7, 5.8,
    7.2, 7.1, 6.7, 5.3, 4.0, 2.5, 1.1, -1.8, 1.3, 3.6, 5.5, 5.9, 4.9, 4.2, 4.4,
    4.3, 4.5,
)

MARCH_SPEC = _spec(
    lot="block-a-march",
    block="Block A",
    first_day="2026-03-01",
    outdoor_C=MARCH_OUTDOOR,
    visits=(
        _visit("2026-03-04", "header", ("09:15", "09:45", "10:15", "10:45")),
        _visit("2026-03-16", "header", ("09:20", "09:50", "10:20")),
        _visit("2026-03-22", "header", ("09:10", "14:10", "14:50")),
        _visit("2026-03-26", "header", ("09:25", "10:00", "10:35")),
    ),
    operations=(
        {
            "day": "2026-03-11",
            "from": "08:00",
            "to": "16:00",
            "entry": "district main pressure test; header room locked off for the day",
        },
        {
            "day": "2026-03-22",
            "from": "13:45",
            "to": "16:15",
            "entry": (
                "changeover on the plant-room set: east riser valved out and the tie-in "
                "interface set isolated; gas plant carrying the block"
            ),
            "held_mixture": CHANGEOVER_MIXTURE,
        },
    ),
    recovery_at_base=0.145,
    gas_at_base=0.350,
    mixture_base_C=3.358,
    sheet_read_on="2026-03-03",
    sheet_outdoor_C=7.5,
    shift_per_C=6.2,
    sample_prefix="ms",
    after_days=(("2026-04-01", 3.4), ("2026-04-02", 2.9), ("2026-04-03", 3.6)),
)


BLOCK_B_SPEC = redrawn(
    CURRENT_SPEC,
    lot="block-b-january",
    block="Block B",
    shift_per_C=2.6,
    noise_lot=CURRENT_SPEC["lot"],
)

_C_CHANGEOVER = {
    "day": "2026-01-12",
    "from": "09:00",
    "to": "11:00",
    "entry": (
        "changeover on the plant-room set: east riser valved out and the tie-in "
        "interface set isolated; gas plant carrying the block"
    ),
    "held_mixture": CHANGEOVER_MIXTURE,
}

BLOCK_C_SPEC = redrawn(
    CURRENT_SPEC,
    lot="block-c-january",
    block="Block C",
    noise_lot=CURRENT_SPEC["lot"],
    operations=(
        JANUARY_OPERATIONS[0],
        _C_CHANGEOVER,
        JANUARY_OPERATIONS[2],
    ),
)


ANNEXE_OUTDOOR = (
    9.6, 10.4, 11.2, 12.1, 11.4, 10.2, 9.1, 8.4, 7.6, 7.2, 7.9, 9.0, 10.1, 11.0,
    11.8, 12.4, 11.5, 10.3, 9.4, 8.6, 7.8, 7.3, 8.1, 9.2, 10.4, 11.3, 10.6, 9.8,
    9.5, 9.7, 9.6,
)

ANNEXE_SPEC = _spec(
    lot="harbour-annexe-march",
    block="Harbour Annexe",
    first_day="2026-03-01",
    outdoor_C=ANNEXE_OUTDOOR,
    visits=(
        _visit("2026-03-03", "header", ("09:15", "09:45", "10:15", "10:45")),
        _visit("2026-03-10", "header", ("09:20", "09:50", "10:20")),
        _visit("2026-03-16", "header", ("09:10", "09:40", "10:10")),
        _visit("2026-03-24", "header", ("09:25", "10:00", "10:35")),
    ),
    operations=(
        {
            "day": "2026-03-13",
            "from": "08:30",
            "to": "12:00",
            "entry": "quay-side crane over the plant room; header room closed to the round",
        },
    ),
    recovery_at_base=0.120,
    gas_at_base=0.395,
    mixture_base_C=9.9,
    sheet_read_on="2026-03-16",
    sheet_outdoor_C=12.4,
    shift_per_C=5.5,
    sample_prefix="as",
    after_days=(("2026-04-01", 8.2), ("2026-04-02", 7.9), ("2026-04-03", 8.4)),
    marker_signature=3.4,
)


CURRENT = build(CURRENT_SPEC)
FEBRUARY = build(FEBRUARY_SPEC)
MARCH = build(MARCH_SPEC)
BLOCK_B = build(BLOCK_B_SPEC)
BLOCK_C = build(BLOCK_C_SPEC)
ANNEXE = build(ANNEXE_SPEC)


LATER = (FEBRUARY, MARCH)


BLOCKS = (BLOCK_B, BLOCK_C)
SHIFT_BLOCK, CHANGEOVER_BLOCK = BLOCKS
OUT_OF_REGIME = ANNEXE


def history_visits(world) -> tuple[dict[str, Any], ...]:
    "The visits behind one lot's frozen history."

    if world.lot == CURRENT.lot:
        return HISTORY_VISITS
    visits = []
    for index, visit in enumerate(world.spec["visits"], start=1):
        visits.append(
            {
                "call_id": f"round-{index:02d}",
                "point": str(visit["point"]),
                "samples": len(visit["at"]),
                "served_on": str(visit["day"]),
            }
        )
    open_days = [str(day) for day, _value in world.spec["after_days"]]
    visits.append(
        {
            "call_id": f"round-{len(visits) + 1:02d}",
            "point": "boiler_house",
            "samples": 3,
            "served_on": str(world.spec["visits"][-1]["day"]),
        }
    )
    visits.append(
        {
            "call_id": "rate-01",
            "point": "tie_in_plant_room",
            "samples": 3,
            "served_on": open_days[0],
        }
    )
    visits.append(
        {
            "call_id": "riser-01",
            "point": "east_riser",
            "samples": 1,
            "dwell_min": 30,
            "served_on": open_days[1],
        }
    )
    return tuple(visits)
