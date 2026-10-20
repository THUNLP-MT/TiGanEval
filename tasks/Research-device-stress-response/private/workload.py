"The qualification lot under review, the ones queued behind it, and the two redraws the audit reads a number's stability off."

from __future__ import annotations

from typing import Any, Mapping

from .world import build, crossing_of, logit


PLAN_HOLD_MIN = 30
SHORT_HOLD_MIN = 5
TARGET_FRACTION = 0.10


def _p50(crossing_bar: float, slope_bar: float) -> float:
    'The pressure at which half the units leak, from where one in ten do.'

    return float(crossing_bar) - float(slope_bar) * logit(TARGET_FRACTION)


def _spec(
    lot: str,
    family: str,
    build_month: str,
    cartridges: Mapping[str, float],
    benches: Mapping[str, float],
    batches: Mapping[str, Mapping[str, Any]],
    crossing_bar: float,
    slope_bar: float,
    *,
    span_bar: float = 250.0,
    block_bar: float = 200.0,
    block_drift_bar: float = 1.2,
    short_hold_min: int = SHORT_HOLD_MIN,
    short_hold_bar: float = 13.0,
    hours_granted: float = 10.0,
    ports: int = 6,
    stores: Mapping[str, int] | None = None,
    bench_out: Mapping[str, tuple[str, str]] | None = None,
    first_review_day: str = "2026-04-08",
    review_day_count: int = 12,
    closes_on: str = "2026-04-19",
    opening_bookings: tuple[Mapping[str, Any], ...] = (),
) -> dict[str, Any]:
    return {
        "lot": lot,
        "family": family,
        "build_month": build_month,
        "cartridges": {name: float(value) for name, value in cartridges.items()},
        "benches": {name: float(value) for name, value in benches.items()},
        "batches": {
            name: {
                "bench": str(batch["bench"]),
                "dwell_min": int(batch["dwell_min"]),
                "cells": {part: int(units) for part, units in batch["cells"].items()},
            }
            for name, batch in batches.items()
        },
        "span_bar": float(span_bar),
        "block_bar": float(block_bar),
        "block_drift_bar": float(block_drift_bar),
        "plan_hold_min": PLAN_HOLD_MIN,
        "short_hold_min": int(short_hold_min),
        "short_hold_bar": float(short_hold_bar),
        "target_fraction": TARGET_FRACTION,
        "slope_bar": float(slope_bar),
        "p50_bar": _p50(crossing_bar, slope_bar),
        "hold_hours": {str(PLAN_HOLD_MIN): 1.0, str(int(short_hold_min)): 0.5},
        "hours_granted": float(hours_granted),
        "ports": int(ports),
        "stores": dict(stores or {"B-05": 20, "B-06": 14}),
        "bench_out": {
            name: (str(window[0]), str(window[1]))
            for name, window in (bench_out or {}).items()
        },
        "first_review_day": str(first_review_day),
        "review_day_count": int(review_day_count),
        "closes_on": str(closes_on),
        "opening_bookings": tuple(dict(item) for item in opening_bookings),
    }


def _ladder(cells: Mapping[str, int]) -> dict[str, int]:
    return {name: int(units) for name, units in cells.items()}


MARCH_CARTRIDGES = {
    "C-140": 151.4,
    "C-200": 186.4,
    "C-215": 201.6,
    "C-255": 240.0,
    "C-275": 262.0,
    "C-300": 288.0,
}

MARCH_BENCHES = {"B-1": 1.0013, "B-2": 0.9200}

MARCH_BATCHES = {
    "B-01": {
        "bench": "B-1",
        "dwell_min": 30,
        "cells": _ladder({name: 60 for name in MARCH_CARTRIDGES}),
    },
    "B-02": {
        "bench": "B-1",
        "dwell_min": 5,
        "cells": _ladder({name: 180 for name in MARCH_CARTRIDGES}),
    },
    "B-03": {
        "bench": "B-2",
        "dwell_min": 30,
        "cells": _ladder({"C-255": 60, "C-275": 60, "C-300": 60}),
    },
    "B-04": {
        "bench": "B-2",
        "dwell_min": 30,
        "cells": _ladder({name: 60 for name in MARCH_CARTRIDGES}),
    },
}


MARCH_OPENING = (
    {
        "booking_id": "qs-0408",
        "bench": "B-1",
        "batch": "B-05",
        "cartridge": "C-215",
        "dwell_min": 30,
        "units": 8,
    },
)

CURRENT_SPEC = _spec(
    lot="qr40-march",
    family="QR-40",
    build_month="2026-03",
    cartridges=MARCH_CARTRIDGES,
    benches=MARCH_BENCHES,
    batches=MARCH_BATCHES,
    crossing_bar=194.0,
    slope_bar=33.0,
    span_bar=203.0,
    short_hold_bar=13.0,
    bench_out={"B-2": ("2026-04-12", "2026-04-15")},
    opening_bookings=MARCH_OPENING,
)


SIBLING_SPECS = (
    _spec(
        lot="qr52-april",
        family="QR-52",
        build_month="2026-04",
        cartridges={
            "C-135": 152.8,
            "C-160": 176.3,
            "C-175": 191.9,
            "C-190": 206.4,
            "C-235": 217.5,
            "C-265": 251.7,
            "C-295": 279.4,
        },
        benches={"B-1": 0.9982, "B-2": 0.9536},
        batches={
            "B-11": {
                "bench": "B-1",
                "dwell_min": 30,
                "cells": _ladder(
                    {"C-135": 260, "C-160": 260, "C-175": 260, "C-190": 260,
                     "C-235": 260, "C-265": 80, "C-295": 80}
                ),
            },
            "B-12": {
                "bench": "B-2",
                "dwell_min": 5,
                "cells": _ladder({"C-160": 200, "C-175": 200, "C-190": 200}),
            },
            "B-13": {
                "bench": "B-2",
                "dwell_min": 30,
                "cells": _ladder(
                    {"C-135": 260, "C-160": 260, "C-175": 260, "C-190": 260,
                     "C-235": 260, "C-265": 80, "C-295": 80}
                ),
            },
        },
        crossing_bar=185.0,
        slope_bar=30.0,
        span_bar=220.0,
        short_hold_bar=11.0,
        hours_granted=8.0,
        stores={"B-21": 18, "B-22": 12},
        bench_out={"B-1": ("2026-05-06", "2026-05-08")},
        first_review_day="2026-05-04",
        closes_on="2026-05-15",
        opening_bookings=(
            {"booking_id": "qs-0504", "bench": "B-2", "batch": "B-21",
             "cartridge": "C-160", "dwell_min": 30, "units": 6},
        ),
    ),
    _spec(
        lot="qr58-april",
        family="QR-58",
        build_month="2026-04",
        cartridges={
            "C-135": 149.7,
            "C-190": 203.6,
            "C-210": 226.1,
            "C-245": 262.4,
            "C-315": 303.8,
        },
        benches={"B-1": 1.0026, "B-3": 0.9611},
        batches={
            "B-21": {
                "bench": "B-1",
                "dwell_min": 30,
                "cells": _ladder(
                    {"C-135": 120, "C-190": 120, "C-210": 120, "C-245": 120, "C-315": 120}
                ),
            },
            "B-22": {
                "bench": "B-3",
                "dwell_min": 5,
                "cells": _ladder({"C-190": 260, "C-210": 260, "C-245": 260}),
            },
            "B-23": {
                "bench": "B-3",
                "dwell_min": 30,
                "cells": _ladder(
                    {"C-135": 120, "C-190": 120, "C-210": 120, "C-245": 120, "C-315": 120}
                ),
            },
        },
        crossing_bar=232.0,
        slope_bar=36.0,
        span_bar=400.0,
        short_hold_bar=15.0,
        hours_granted=7.0,
        stores={"B-31": 16, "B-32": 10},
        bench_out={"B-3": ("2026-05-19", "2026-05-21")},
        first_review_day="2026-05-18",
        closes_on="2026-05-29",
        opening_bookings=(
            {"booking_id": "qs-0518", "bench": "B-1", "batch": "B-31",
             "cartridge": "C-210", "dwell_min": 30, "units": 9},
        ),
    ),
    _spec(
        lot="qr61-may",
        family="QR-61",
        build_month="2026-05",
        cartridges={
            "C-110": 122.5,
            "C-170": 153.9,
            "C-195": 179.6,
            "C-250": 236.7,
            "C-280": 264.1,
            "C-315": 301.3,
        },
        benches={"B-2": 0.9487, "B-4": 1.0041},
        batches={
            "B-31": {
                "bench": "B-4",
                "dwell_min": 30,
                "cells": _ladder(
                    {"C-110": 130, "C-170": 130, "C-195": 130, "C-250": 130,
                     "C-280": 130, "C-315": 130}
                ),
            },
            "B-32": {
                "bench": "B-2",
                "dwell_min": 10,
                "cells": _ladder({"C-170": 280, "C-195": 280, "C-250": 280}),
            },
            "B-33": {
                "bench": "B-2",
                "dwell_min": 30,
                "cells": _ladder(
                    {"C-110": 130, "C-170": 130, "C-195": 130, "C-250": 130,
                     "C-280": 130, "C-315": 130}
                ),
            },
        },
        crossing_bar=168.0,
        slope_bar=31.0,
        span_bar=220.0,
        short_hold_min=10,
        short_hold_bar=12.0,
        hours_granted=9.0,
        stores={"B-41": 22, "B-42": 14},
        bench_out={"B-2": ("2026-06-09", "2026-06-11")},
        first_review_day="2026-06-08",
        closes_on="2026-06-19",
        opening_bookings=(
            {"booking_id": "qs-0608", "bench": "B-4", "batch": "B-41",
             "cartridge": "C-170", "dwell_min": 30, "units": 6},
        ),
    ),
)


OUT_OF_REGIME_SPEC = _spec(
    lot="qr73-june",
    family="QR-73",
    build_month="2026-06",
    cartridges={
        "C-215": 203.1,
        "C-230": 244.6,
        "C-270": 286.9,
        "C-305": 322.4,
        "C-345": 361.8,
    },
    benches={"B-5": 1.0004, "B-6": 0.9996},
    batches={
        "B-41": {
            "bench": "B-5",
            "dwell_min": 30,
            "cells": _ladder(
                {"C-215": 140, "C-230": 140, "C-270": 140, "C-305": 140, "C-345": 140}
            ),
        },
        "B-42": {
            "bench": "B-6",
            "dwell_min": 30,
            "cells": _ladder(
                {"C-215": 140, "C-230": 140, "C-270": 140, "C-305": 140, "C-345": 140}
            ),
        },
    },
    crossing_bar=358.0,
    slope_bar=38.0,
    span_bar=400.0,
    hours_granted=6.0,
    stores={"B-51": 18, "B-52": 12},
    bench_out={"B-6": ("2026-07-13", "2026-07-14")},
    first_review_day="2026-07-10",
    closes_on="2026-07-21",
    opening_bookings=(
        {"booking_id": "qs-0710", "bench": "B-5", "batch": "B-51",
         "cartridge": "C-305", "dwell_min": 30, "units": 6},
    ),
)


ENDPOINT_SPEC = _spec(
    lot="qr79-july",
    family="QR-79",
    build_month="2026-07",
    cartridges={
        "C-125": 140.0,
        "C-175": 160.0,
        "C-170": 180.0,
        "C-215": 200.0,
        "C-208": 220.0,
    },
    benches={"B-7": 1.0, "B-8": 1.0},
    batches={
        "B-51": {
            "bench": "B-7",
            "dwell_min": 30,
            "cells": _ladder(
                {"C-125": 100, "C-175": 2, "C-170": 2, "C-215": 2,
                 "C-208": 4}
            ),
        },
        "B-52": {
            "bench": "B-8",
            "dwell_min": 30,
            "cells": _ladder(
                {"C-125": 100, "C-175": 2, "C-170": 1, "C-215": 1,
                 "C-208": 4}
            ),
        },
    },
    crossing_bar=171.55,
    slope_bar=8.0,
    span_bar=280.0,
    hours_granted=0.0,
    stores={"B-61": 12},
    bench_out={},
    first_review_day="2026-08-03",
    review_day_count=3,
    closes_on="2026-08-05",
)


def _variant(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    grown = dict(spec)
    grown.update(changes)
    return grown


PARTNER_SPECS = (
    _variant(
        CURRENT_SPEC,
        lot="qr40-march-recalibrated",
        benches={"B-1": 0.8800, "B-2": 0.9500},
    ),
    _variant(
        CURRENT_SPEC,
        lot="qr40-march-reissued",
        batches={
            name: {**batch, "bench": "B-2"} for name, batch in MARCH_BATCHES.items()
        },
    ),
)


CURRENT = build(CURRENT_SPEC)
SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)
OUT_OF_REGIME = build(OUT_OF_REGIME_SPEC)
ENDPOINT = build(ENDPOINT_SPEC)
PARTNERS = tuple(build(spec) for spec in PARTNER_SPECS)


SCALE_PARTNER, BENCH_PARTNER = PARTNERS

PLAN_CROSSING = crossing_of(CURRENT_SPEC, PLAN_HOLD_MIN)
