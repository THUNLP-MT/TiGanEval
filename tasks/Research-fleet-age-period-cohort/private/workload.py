'The region under review, the regions the same notebook is run on next, and the region whose depots never changed card.'

from __future__ import annotations

from typing import Any, Mapping

from . import fleet, world


BASE_CARD = "WA-30"
NEW_CARD = "WA-52"


def _cards(depots, change) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for depot in depots:
        if change and depot == change["depot"]:
            rows.append(
                {
                    "depot": depot,
                    "walkaround_ref": BASE_CARD,
                    "from_month": "2020-06",
                    "to_month": world.month_label(world.month_key(change["from_month"]) - 1),
                }
            )
            rows.append(
                {
                    "depot": depot,
                    "walkaround_ref": str(change["to_card"]),
                    "from_month": str(change["from_month"]),
                    "to_month": None,
                }
            )
        else:
            rows.append(
                {
                    "depot": depot,
                    "walkaround_ref": BASE_CARD,
                    "from_month": "2020-06",
                    "to_month": None,
                }
            )
    return rows


_CHANGE_NOTES = (
    "floor pan gauge",
    "rear door seal",
    "loading bay lamp",
    "front hub carrier",
    "wiring loom route",
    "handbrake lever",
    "bulkhead bracket",
    "roof rail mount",
    "fuel filler neck",
    "step tread finish",
    "mirror arm casting",
    "load restraint eye",
    "cab floor mat",
)


def _sheets_and_orders(
    builds, steps: tuple[int, ...], lot_prefix: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    orders: list[dict[str, Any]] = []
    sheets: list[dict[str, Any]] = []
    segment_of: dict[str, int] = {}
    segment = 0
    spec_index = 4
    lot_serial = 2040
    lots = [f"L-{lot_serial}", f"L-{lot_serial + 1}"]
    for index, build in enumerate(builds):
        if index in steps:
            segment += 1
            spec_index += 1
            lot_serial += 3
            lots = [f"L-{lot_serial}", f"L-{lot_serial + 1}"]
            orders.append(
                {
                    "order_id": f"CO-{100 + len(orders) * 7}",
                    "effective_build_month": build,
                    "body_spec": f"BS-{spec_index}",
                    "change": _CHANGE_NOTES[len(orders) % len(_CHANGE_NOTES)],
                }
            )
        segment_of[build] = segment
        sheets.append(
            {
                "build_month": build,
                "body_spec": f"BS-{spec_index}",
                "lots": [f"{lot_prefix}{name}" for name in lots],
            }
        )
    return sheets, orders, segment_of


def _spec(
    *,
    region: str,
    label: str,
    depots: tuple[str, ...],
    van_prefix: str,
    fault_prefix: str,
    lot_prefix: str,
    per_build: tuple[int, int],
    cohort_boost: float,
    draw: int,
    card: Mapping[str, Any] | None,
    short_lease_months: int | None,
    order_steps: tuple[int, ...],
    named_pair: tuple[str, str],
    truth_points: float,
    base_rate: float,
    days_granted: int,
    as_of: str,
) -> dict[str, Any]:
    builds = world.month_span("2020-06", 33)
    sheets, orders, segment_of = _sheets_and_orders(builds, order_steps, lot_prefix)
    shares = {
        "default": [0.22, 0.44, 0.34][: len(depots)] + [0.20] * max(0, len(depots) - 3),
        "2022-H2": [0.66, 0.20, 0.14][: len(depots)] + [0.12] * max(0, len(depots) - 3),
    }
    short = (
        None
        if short_lease_months is None
        else {"group": "2022-H2", "months": int(short_lease_months),
              "lease_ref": f"L-{int(short_lease_months)}"}
    )
    return {
        "region": region,
        "label": label,
        "depots": depots,
        "van_prefix": van_prefix,
        "fault_prefix": fault_prefix,
        "first_return": "2022-04",
        "returns": 24,
        "first_build": "2020-06",
        "builds": 33,
        "per_build": per_build,
        "cohort_boost": float(cohort_boost),
        "draw": int(draw),
        "depot_shares": shares,
        "transfer_rate": 0.04,
        "lease_ref": "L-36",
        "lease_months": 36,
        "short_lease": short,
        "base_card": BASE_CARD,
        "card": card,
        "cards": _cards(depots, card),
        "leases": [
            {"lease_ref": "L-36", "term_months": 36},
            *([] if short is None else [{"lease_ref": short["lease_ref"],
                                        "term_months": short["months"]}]),
        ],
        "build_sheets": sheets,
        "change_orders": orders,
        "build_segment": segment_of,
        "named_pair": named_pair,
        "compare": ("2021-H2", "2022-H2"),
        "truth_points": float(truth_points),
        "base_rate": float(base_rate),
        "age_slope": 0.22,
        "build_trend": 0.24,
        "days_granted": int(days_granted),
        "days_per_week": 4,
        "vans_per_day": 25,
        "vans_in_service_minimum": 10,
        "range_bar_points": 1.0,
        "regions_on_the_note": 4,
        "one_time_in": 20,
        "tolerance_points": 0.4,
        "as_of": as_of,
    }


CURRENT_SPEC = _spec(
    region="ryecourt",
    label="Ryecourt",
    depots=("Kestrel", "Ardmore", "Sallow"),
    van_prefix="RY",
    fault_prefix="RF",
    lot_prefix="",
    per_build=(46, 58),
    cohort_boost=1.0,
    draw=510_2201,
    card={"depot": "Kestrel", "from_month": "2022-09", "to_card": NEW_CARD, "factor": 1.7},
    short_lease_months=14,
    order_steps=(8, 16, 25, 31),
    named_pair=("2021-03", "2021-04"),
    truth_points=-0.6,
    base_rate=1.2,
    days_granted=18,
    as_of="2024-04-08",
)


LINTHORPE_SPEC = dict(
    CURRENT_SPEC,
    region="linthorpe",
    label="Linthorpe",
    depots=("Kestrel", "Ardmore", "Sallow"),
    van_prefix="LP",
    fault_prefix="LF",
    draw=511_3307,
    card={"depot": "Kestrel", "from_month": "2023-02", "to_card": NEW_CARD, "factor": 1.32},
)
LINTHORPE_SPEC["cards"] = _cards(LINTHORPE_SPEC["depots"], LINTHORPE_SPEC["card"])

WARDLEY_SPEC = dict(
    CURRENT_SPEC,
    region="wardley",
    label="Wardley",
    van_prefix="WD",
    fault_prefix="WDF",
    draw=512_4409,
    short_lease={"group": "2022-H2", "months": 20, "lease_ref": "L-20"},
    leases=[{"lease_ref": "L-36", "term_months": 36}, {"lease_ref": "L-20", "term_months": 20}],
)

FOLLOWING_SPECS = (
    _spec(
        region="marbeck",
        label="Marbeck",
        depots=("Hallam", "Bracken", "Toller", "Quinn"),
        van_prefix="MB",
        fault_prefix="MF",
        lot_prefix="M",
        per_build=(26, 34),
        cohort_boost=1.0,
        draw=620_5503,
        card={"depot": "Hallam", "from_month": "2022-07", "to_card": NEW_CARD, "factor": 1.85},
        short_lease_months=16,
        order_steps=(10, 18, 25, 31),
        named_pair=("2020-11", "2020-12"),
        truth_points=-1.8,
        base_rate=1.5,
        days_granted=16,
        as_of="2024-04-08",
    ),
    _spec(
        region="corriden",
        label="Corriden",
        depots=("Marrow", "Pilling", "Denby"),
        van_prefix="CD",
        fault_prefix="CF",
        lot_prefix="C",
        per_build=(26, 34),
        cohort_boost=1.0,
        draw=730_6607,
        card={"depot": "Marrow", "from_month": "2022-11", "to_card": NEW_CARD, "factor": 1.5},
        short_lease_months=13,
        order_steps=(9, 17, 25, 31),
        named_pair=("2022-01", "2022-02"),
        truth_points=1.0,
        base_rate=1.0,
        days_granted=20,
        as_of="2024-04-08",
    ),
    _spec(
        region="halloway",
        label="Halloway",
        depots=("Ferrers", "Oakhill", "Winsley"),
        van_prefix="HW",
        fault_prefix="HF",
        lot_prefix="H",
        per_build=(26, 34),
        cohort_boost=1.0,
        draw=840_7709,
        card={"depot": "Ferrers", "from_month": "2022-10", "to_card": NEW_CARD, "factor": 1.65},
        short_lease_months=15,
        order_steps=(16, 25, 31),
        named_pair=("2021-09", "2021-10"),
        truth_points=-0.9,
        base_rate=1.7,
        days_granted=18,
        as_of="2024-04-08",
    ),
)


LIFTED_SPEC = _spec(
    region="wexbury",
    label="Wexbury",
    depots=("Caldon", "Rathe", "Ingleby"),
    van_prefix="WX",
    fault_prefix="WF",
    lot_prefix="W",
    per_build=(26, 34),
    cohort_boost=1.0,
    draw=950_8811,
    card=None,
    short_lease_months=None,
    order_steps=(9, 18, 25, 31),
    named_pair=("2023-01", "2023-02"),
    truth_points=0.3,
    base_rate=1.4,
    days_granted=18,
    as_of="2024-04-08",
)


_CACHE: dict[str, world.Region] = {}


def region(spec: Mapping[str, Any]) -> world.Region:
    key = str(spec["region"])
    if key not in _CACHE:
        _CACHE[key] = fleet.build_region(spec)
    return _CACHE[key]


def current() -> world.Region:
    return region(CURRENT_SPEC)


def linthorpe() -> world.Region:
    return region(LINTHORPE_SPEC)


def wardley() -> world.Region:
    return region(WARDLEY_SPEC)


def following() -> tuple[world.Region, ...]:
    return tuple(region(spec) for spec in FOLLOWING_SPECS)


def lifted() -> world.Region:
    return region(LIFTED_SPEC)


def every_region() -> tuple[world.Region, ...]:
    return (current(), linthorpe(), wardley(), *following(), lifted())
