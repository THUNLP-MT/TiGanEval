"The soak campaign under review, the ones queued behind it, and the two redraws the audit reads a figure's stability off."

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .world import World, build_catalogue, shape


FIELD_DRIVE_A = 1.4
HOLD_TEMP_C = 85.0
TARGET_LOSS = 0.10
READ_INTERVAL_H = 48.0
BLOCK_READ_INTERVAL_H = 12.0


MARCH_CATALOGUE = {
    "defect_growth": {
        "time_shape": "power",
        "shape_constant": 0.66,
        "drive_form": "exponential",
        "drive_constant": 2.1993,
        "ten_degree_factor": 1.7,
    },
    "interface_creep": {
        "time_shape": "logarithmic",
        "shape_constant": 760.0,
        "drive_form": "power",
        "drive_constant": 3.4,
        "ten_degree_factor": 3.4,
    },
    "contact_oxide": {
        "time_shape": "saturating",
        "shape_constant": 400.0,
        "drive_form": "power",
        "drive_constant": 3.4,
        "ten_degree_factor": 2.2,
    },
    "drive_fatigue": {
        "time_shape": "linear",
        "shape_constant": 1000.0,
        "drive_form": "exponential",
        "drive_constant": 2.1993,
        "ten_degree_factor": 1.3,
    },
}


def amplitude_for(catalogue: Mapping[str, Any], law: str, hours: float) -> float:
    "The amplitude that puts one law's tenth-lost point at these hours."

    entry = catalogue[law]
    return TARGET_LOSS / shape(
        str(entry["time_shape"]), float(entry["shape_constant"]), float(hours)
    )


def modules(
    rows: Sequence[tuple[str, str, float, int, float]],
    started: Mapping[str, str],
    incoming: Sequence[float],
) -> list[dict[str, Any]]:
    'One module row per emitter: its lot, rack, drive, incoming and reach.'

    out: list[dict[str, Any]] = []
    for lot, rack, drive, count, reach in rows:
        for index in range(int(count)):
            number = len(out) + 1
            out.append(
                {
                    "module_id": f"{lot}-{number:02d}",
                    "lot": lot,
                    "rack": rack,
                    "drive_a": float(drive),
                    "incoming_mw": float(incoming[(number - 1) % len(incoming)]),
                    "started_on": str(started[rack]),
                    "reach_h": float(reach),
                }
            )
    return out


def spec(
    campaign: str,
    family: str,
    build_month: str,
    law: str,
    hours_to_target: float,
    module_rows: Sequence[dict[str, Any]],
    racks: Mapping[str, int],
    *,
    field_drive_a: float = FIELD_DRIVE_A,
    hold_temp_c: float = HOLD_TEMP_C,
    catalogue: Mapping[str, Any] = MARCH_CATALOGUE,
    meter_full_scale_mw: float = 40.0,
    read_noise_mw: float = 0.10,
    reference_source_mw: float = 20.0,
    days_granted: int = 16,
    ports_cap: int = 8,
    days_per_block_cap: int = 4,
    drive_cap_a: float = 1.8,
    drive_floor_a: float = 1.0,
    temp_cap_c: float = 95.0,
    smallest_block_days: int = 2,
    review_acts_within_h: float = 350.0,
    spares: Mapping[str, int] | None = None,
    spare_incoming_mw: Mapping[str, float] | None = None,
    rig_out: Sequence[str] = (),
    first_day: str = "2026-03-09",
    day_count: int = 18,
    review_on: str = "2026-03-26",
    opening_blocks: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "campaign": campaign,
        "family": family,
        "build_month": build_month,
        "field_drive_a": float(field_drive_a),
        "hold_temp_c": float(hold_temp_c),
        "target_loss": TARGET_LOSS,
        "read_interval_h": READ_INTERVAL_H,
        "block_read_interval_h": BLOCK_READ_INTERVAL_H,
        "catalogue": build_catalogue(catalogue),
        "law": law,
        "law_amplitude": amplitude_for(catalogue, law, hours_to_target),
        "modules": [dict(item) for item in module_rows],
        "racks": {name: int(value) for name, value in racks.items()},
        "meter_full_scale_mw": float(meter_full_scale_mw),
        "read_noise_mw": float(read_noise_mw),
        "reference_source_mw": float(reference_source_mw),
        "days_granted": int(days_granted),
        "ports_cap": int(ports_cap),
        "days_per_block_cap": int(days_per_block_cap),
        "drive_cap_a": float(drive_cap_a),
        "drive_floor_a": float(drive_floor_a),
        "temp_cap_c": float(temp_cap_c),
        "smallest_block_days": int(smallest_block_days),
        "review_acts_within_h": float(review_acts_within_h),
        "spares": dict(spares or {"L-19": 7, "L-22": 5}),
        "spare_incoming_mw": dict(spare_incoming_mw or {"L-19": 40.7, "L-22": 40.7}),
        "rig_out": list(rig_out),
        "first_day": str(first_day),
        "day_count": int(day_count),
        "review_on": str(review_on),
        "opening_blocks": tuple(dict(item) for item in opening_blocks),
    }


MARCH_INCOMING = (40.7, 41.1, 40.5, 40.9, 41.2, 40.6, 41.0, 40.8)


MARCH_MODULES = modules(
    rows=(
        ("L-11", "R-A", 1.4, 6, 1680.0),
        ("L-17", "R-A", 1.4, 5, 1440.0),
        ("L-22", "R-A", 1.7, 3, 864.0),
        ("L-14", "R-B", 1.4, 6, 1536.0),
        ("L-14", "R-B", 1.7, 4, 768.0),


        ("L-11", "R-A", 1.4, 1, 0.0),
    ),
    started={"R-A": "2026-01-05 08:00", "R-B": "2026-01-19 08:00"},
    incoming=MARCH_INCOMING,
)


MARCH_OPENING = (
    {
        "block_id": "cb-0309",
        "drive_a": 2.1,
        "case_temp_c": 85.0,
        "ports": 8,
        "chamber_days": 2,
        "lot": "L-19",
    },
)

CURRENT_SPEC = spec(
    campaign="em9-march",
    family="EM-9",
    build_month="2026-03",
    law="defect_growth",
    hours_to_target=2450.0,
    module_rows=MARCH_MODULES,
    racks={"R-A": 60, "R-B": 30},
    rig_out=("2026-03-14", "2026-03-16"),
    opening_blocks=MARCH_OPENING,
)


def _catalogue(**changes: Mapping[str, Any]) -> dict[str, Any]:
    out = {name: dict(entry) for name, entry in MARCH_CATALOGUE.items()}
    for name, entry in changes.items():
        out[name].update(entry)
    return out


APRIL_CATALOGUE = _catalogue(
    defect_growth={"shape_constant": 0.71},
    interface_creep={"shape_constant": 620.0},
    contact_oxide={"shape_constant": 500.0},
)

JUNE_CATALOGUE = _catalogue(
    defect_growth={"shape_constant": 0.62, "drive_constant": 2.4},
    interface_creep={"shape_constant": 700.0, "drive_constant": 3.7},
    contact_oxide={"shape_constant": 340.0, "drive_constant": 3.7},
    drive_fatigue={"drive_constant": 2.4},
)

SUMMER_CATALOGUE = _catalogue(
    defect_growth={"shape_constant": 0.71},
    interface_creep={"shape_constant": 800.0},
    contact_oxide={"shape_constant": 500.0},
)

AUGUST_CATALOGUE = _catalogue(
    defect_growth={"shape_constant": 0.62, "drive_constant": 2.4},
    interface_creep={"shape_constant": 500.0, "drive_constant": 3.7},
    contact_oxide={"shape_constant": 340.0, "drive_constant": 3.7},
    drive_fatigue={"drive_constant": 2.4},
)

SIBLING_SPECS = (
    spec(
        campaign="em9-april",
        family="EM-9",
        build_month="2026-04",
        law="interface_creep",
        hours_to_target=1980.0,
        catalogue=APRIL_CATALOGUE,
        module_rows=modules(
            rows=(
                ("L-26", "R-A", 1.4, 5, 1344.0),
                ("L-26", "R-A", 1.7, 3, 720.0),
                ("L-31", "R-B", 1.4, 6, 1200.0),
                ("L-33", "R-B", 1.7, 4, 672.0),
            ),
            started={"R-A": "2026-02-02 08:00", "R-B": "2026-02-16 08:00"},
            incoming=(41.3, 41.7, 41.5, 41.9, 41.2, 41.6),
        ),
        racks={"R-A": 60, "R-B": 60},
        days_granted=13,
        review_acts_within_h=350.0,
        spares={"L-38": 6, "L-40": 4},
        spare_incoming_mw={"L-38": 40.7, "L-40": 40.7},
        rig_out=("2026-04-20", "2026-04-21"),
        first_day="2026-04-13",
        day_count=16,
        review_on="2026-04-29",
        opening_blocks=(
            {"block_id": "cb-0413", "drive_a": 1.6, "case_temp_c": 99.0, "ports": 6,
             "chamber_days": 2, "lot": "L-38"},
        ),
    ),
    spec(
        campaign="em11-june",
        family="EM-11",
        build_month="2026-06",
        law="defect_growth",
        hours_to_target=3050.0,
        catalogue=JUNE_CATALOGUE,
        meter_full_scale_mw=45.0,
        module_rows=modules(
            rows=(
                ("L-52", "R-C", 1.4, 7, 1824.0),
                ("L-55", "R-C", 1.7, 4, 960.0),
                ("L-58", "R-D", 1.4, 6, 1632.0),
                ("L-58", "R-D", 1.7, 3, 912.0),
            ),
            started={"R-C": "2026-04-06 08:00", "R-D": "2026-04-20 08:00"},
            incoming=(45.8, 46.2, 45.6, 46.0, 46.4, 45.9),
        ),
        racks={"R-C": 60, "R-D": 60},
        days_granted=15,
        review_acts_within_h=250.0,
        spares={"L-61": 8, "L-63": 5},
        spare_incoming_mw={"L-61": 45.8, "L-63": 45.8},
        rig_out=("2026-06-17", "2026-06-18"),
        first_day="2026-06-12",
        day_count=17,
        review_on="2026-06-28",
        opening_blocks=(
            {"block_id": "cb-0612", "drive_a": 1.4, "case_temp_c": 85.0, "ports": 9,
             "chamber_days": 2, "lot": "L-61"},
        ),
    ),
    spec(
        campaign="em14-june",
        family="EM-14",
        build_month="2026-06",
        law="defect_growth",
        hours_to_target=2150.0,
        field_drive_a=1.0,
        hold_temp_c=80.0,
        catalogue=SUMMER_CATALOGUE,
        module_rows=modules(
            rows=(
                ("L-70", "R-E", 1.4, 7, 1488.0),
                ("L-72", "R-E", 1.7, 4, 768.0),
                ("L-74", "R-F", 1.4, 8, 1392.0),
                ("L-77", "R-F", 1.7, 4, 720.0),
            ),
            started={"R-E": "2026-04-13 08:00", "R-F": "2026-04-27 08:00"},
            incoming=(40.8, 41.1, 40.6, 41.0, 40.7, 41.2, 40.9),
        ),
        racks={"R-E": 60, "R-F": 60},
        days_granted=12,
        review_acts_within_h=380.0,
        spares={"L-80": 7, "L-82": 6},
        spare_incoming_mw={"L-80": 40.7, "L-82": 40.7},
        rig_out=("2026-06-24", "2026-06-25"),
        first_day="2026-06-19",
        day_count=15,
        review_on="2026-07-03",
        opening_blocks=(
            {"block_id": "cb-0619", "drive_a": 1.5, "case_temp_c": 88.0, "ports": 6,
             "chamber_days": 1, "lot": "L-80"},
        ),
    ),
)


OUT_OF_REGIME_SPEC = spec(
    campaign="em18-august",
    family="EM-18",
    build_month="2026-08",
    law="defect_growth",
    hours_to_target=2620.0,
    catalogue=AUGUST_CATALOGUE,
    meter_full_scale_mw=60.0,
    module_rows=modules(
        rows=(
            ("L-88", "R-G", 1.4, 6, 4128.0),
            ("L-90", "R-G", 1.7, 4, 2160.0),
            ("L-93", "R-H", 1.4, 6, 3648.0),
            ("L-95", "R-H", 1.7, 4, 1920.0),
        ),
        started={"R-G": "2026-02-09 08:00", "R-H": "2026-03-09 08:00"},
        incoming=(45.9, 46.3, 45.7, 46.1, 46.5, 46.0),
    ),
    racks={"R-G": 60, "R-H": 60},
    days_granted=11,
    drive_cap_a=1.5,
    temp_cap_c=90.0,
    review_acts_within_h=300.0,
    spares={"L-97": 6, "L-99": 4},
    spare_incoming_mw={"L-97": 46.0, "L-99": 46.0},
    rig_out=("2026-08-20", "2026-08-21"),
    first_day="2026-08-14",
    day_count=15,
    review_on="2026-08-28",
    opening_blocks=(
        {"block_id": "cb-0814", "drive_a": 1.4, "case_temp_c": 85.0, "ports": 6,
         "chamber_days": 2, "lot": "L-97"},
    ),
)


def _redraw(base: Mapping[str, Any], campaign: str, racks: Mapping[str, int]) -> dict[str, Any]:
    grown = dict(base)
    grown["campaign"] = campaign
    grown["racks"] = {name: int(value) for name, value in racks.items()}
    return grown


PARTNER_SPECS = (
    _redraw(CURRENT_SPEC, "em9-march-recadenced", {"R-A": 60, "R-B": 15}),
    _redraw(CURRENT_SPEC, "em9-march-rebuild-moved", {"R-A": 30, "R-B": 60}),
)


CURRENT = World(spec=CURRENT_SPEC)
SIBLINGS = tuple(World(spec=item) for item in SIBLING_SPECS)
OUT_OF_REGIME = World(spec=OUT_OF_REGIME_SPEC)
PARTNERS = tuple(World(spec=item) for item in PARTNER_SPECS)


CADENCE_PARTNER, REBUILD_PARTNER = PARTNERS
