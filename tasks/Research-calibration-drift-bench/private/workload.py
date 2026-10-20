'The campaign on the bench now, the ones that follow it, and the one out of regime.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .world import build


def _lot(lot: str, supplier: str, day: int, plan: Sequence[int], spares: int = 0) -> dict[str, Any]:
    return {
        "lot": lot,
        "supplier": supplier,
        "arrived_day": int(day),
        "rig_plan": [int(rig) for rig in plan],
        "spares": int(spares),
    }


def _spec(
    campaign: str,
    draw: int,
    mu_a: float,
    ratio: float,
    lots: Sequence[Mapping[str, Any]],
    calibration_days: Mapping[int, Sequence[int]],
    beta: Mapping[int, float],
    fixture_ratio: float,
    rig2_installed_day: int,
    review_day: int,
    bench_hours_left: float,
    rig_hours_available: Mapping[int, float],
    premium: float,
    lot_sd: float = 0.15,
    part_sd: float = 0.025,
    noise_sd: float = 0.12,
    reference_noise: float = 0.15,
    reference_run_every: int = 5,
) -> dict[str, Any]:
    return {
        "campaign": campaign,
        "draw": int(draw),
        "mu_a": float(mu_a),
        "ratio": float(ratio),
        "lots": [dict(entry) for entry in lots],
        "calibration_days": {int(rig): [int(day) for day in days]
                             for rig, days in calibration_days.items()},
        "beta": {int(rig): float(value) for rig, value in beta.items()},
        "fixture": {1: 1.0, 2: float(fixture_ratio)},
        "rigs": [
            {"rig": 1, "fixture": "FX-40", "installed_day": 1,
             "contact_radius_mm": 4.0},
            {"rig": 2, "fixture": "FX-52", "installed_day": int(rig2_installed_day),
             "contact_radius_mm": 5.2},
        ],
        "review_day": int(review_day),
        "bench_hours_left": float(bench_hours_left),
        "rig_hours_available": {int(rig): float(value)
                                for rig, value in rig_hours_available.items()},
        "hours": {"part": 2.0, "reference": 0.5},
        "reference_block_um": 20.0,
        "reference_noise": float(reference_noise),
        "reference_run_every": int(reference_run_every),
        "lot_sd": float(lot_sd),
        "part_sd": float(part_sd),
        "noise_sd": float(noise_sd),
        "quotes": {"unit_price_premium_b": float(premium)},
        "stores": [],
    }


def _with_stores(spec: dict[str, Any]) -> dict[str, Any]:
    'Name the spare parts each lot shipped, which is what stores still holds.'

    stores = []
    for lot in spec["lots"]:
        run = len(lot["rig_plan"])
        for offset in range(int(lot["spares"])):
            stores.append({
                "part": f"{lot['lot']}-{run + offset + 1:02d}",
                "lot": lot["lot"],
                "supplier": lot["supplier"],
            })
    spec["stores"] = stores
    return spec


CURRENT_SPEC = _with_stores(_spec(
    campaign="bushing-qualification-2026",
    draw=5319,
    mu_a=11.8,
    ratio=0.98,
    lots=[
        _lot("A-3308", "A", 3, [1] * 9, spares=1),
        _lot("A-3312", "A", 9, [1] * 9),
        _lot("A-3317", "A", 15, [1] * 9),
        _lot("A-3321", "A", 22, [1] * 9, spares=1),
        _lot("A-3330", "A", 40, [1, 1, 1, 1, 1, 1, 1, 2], spares=3),
        _lot("A-3336", "A", 68, [2] * 4, spares=1),
        _lot("B-7101", "B", 33, [2] * 9),
        _lot("B-7108", "B", 44, [2] * 9),
        _lot("B-7115", "B", 52, [2] * 9, spares=1),
        _lot("B-7122", "B", 62, [1, 1, 2, 2, 2, 2, 2, 2, 2, 2], spares=3),
        _lot("B-7130", "B", 74, [1] * 9, spares=1),
    ],
    calibration_days={1: [1, 39, 60, 73], 2: [30, 44, 58]},
    beta={1: 0.0030, 2: 0.0014},
    fixture_ratio=0.82,
    rig2_installed_day=30,
    review_day=85,


    bench_hours_left=12.0,
    rig_hours_available={1: 24.0, 2: 8.0},
    premium=0.11,
))

CURRENT = build(CURRENT_SPEC)


SPENT_RUNS = (
    {"rig": 1, "reference_block": True},
    {"rig": 2, "reference_block": True},
)
SPENT_IDS = ("kt-block-r1", "kt-block-r2")


SIBLING_SPECS = (
    _with_stores(_spec(
        campaign="thrust-washer-2026",
        draw=8374,
        mu_a=13.4,
        ratio=1.01,
        lots=[
            _lot("A-4102", "A", 2, [1] * 8),
            _lot("A-4108", "A", 8, [1] * 8, spares=1),
            _lot("A-4114", "A", 14, [1] * 8),
            _lot("A-4120", "A", 21, [1] * 8, spares=1),
            _lot("A-4129", "A", 38, [1, 1, 1, 1, 1, 1, 2, 2], spares=2),
            _lot("A-4135", "A", 64, [2] * 5, spares=1),
            _lot("B-8201", "B", 30, [2] * 9),
            _lot("B-8209", "B", 41, [2] * 10),
            _lot("B-8216", "B", 50, [2] * 9, spares=1),
            _lot("B-8224", "B", 59, [1, 1, 1, 2, 2, 2, 2, 2, 2], spares=2),
            _lot("B-8232", "B", 70, [1] * 6, spares=1),
        ],
        calibration_days={1: [1, 37, 57, 69], 2: [28, 43, 56]},
        beta={1: 0.0019, 2: 0.0008},
        fixture_ratio=0.85,
        rig2_installed_day=28,
        review_day=80,
        bench_hours_left=20.0,
        rig_hours_available={1: 20.0, 2: 6.0},
        premium=0.09,
    )),
    _with_stores(_spec(
        campaign="guide-bush-2026",
        draw=6938,
        mu_a=9.6,
        ratio=0.955,
        lots=[
            _lot("A-5011", "A", 4, [1] * 7),
            _lot("A-5018", "A", 11, [1] * 7, spares=1),
            _lot("A-5024", "A", 18, [1] * 7),
            _lot("A-5031", "A", 26, [1] * 8, spares=1),
            _lot("A-5040", "A", 44, [1, 1, 1, 1, 1, 2, 2], spares=3),
            _lot("A-5047", "A", 70, [2] * 6, spares=1),
            _lot("B-9301", "B", 36, [2] * 10),
            _lot("B-9310", "B", 47, [2] * 9),
            _lot("B-9318", "B", 55, [2] * 9, spares=1),
            _lot("B-9327", "B", 64, [1, 1, 2, 2, 2, 2, 2, 2, 2], spares=3),
            _lot("B-9335", "B", 76, [1] * 8, spares=1),
        ],
        calibration_days={1: [1, 43, 62, 75], 2: [34, 46, 60]},
        beta={1: 0.0029, 2: 0.0012},
        fixture_ratio=0.86,
        rig2_installed_day=34,
        review_day=88,
        bench_hours_left=26.0,
        rig_hours_available={1: 26.0, 2: 10.0},
        premium=0.14,
    )),
    _with_stores(_spec(
        campaign="pivot-bush-2027",
        draw=4258,
        mu_a=15.2,
        ratio=0.99,
        lots=[
            _lot("A-6203", "A", 5, [1] * 8),
            _lot("A-6211", "A", 12, [1] * 8, spares=1),
            _lot("A-6219", "A", 19, [1] * 7),
            _lot("A-6226", "A", 27, [1] * 7, spares=1),
            _lot("A-6234", "A", 42, [1, 1, 1, 1, 1, 1, 2, 2, 2], spares=2),
            _lot("A-6241", "A", 67, [2] * 4, spares=1),
            _lot("B-1402", "B", 35, [2] * 9),
            _lot("B-1411", "B", 45, [2] * 9),
            _lot("B-1419", "B", 53, [2] * 10, spares=1),
            _lot("B-1428", "B", 63, [1, 1, 1, 1, 2, 2, 2, 2, 2], spares=2),
            _lot("B-1436", "B", 75, [1] * 7, spares=1),
        ],
        calibration_days={1: [1, 41, 61, 74], 2: [33, 44, 59]},
        beta={1: 0.0022, 2: 0.0006},
        fixture_ratio=0.85,
        rig2_installed_day=33,
        review_day=86,
        bench_hours_left=22.0,
        rig_hours_available={1: 22.0, 2: 8.0},
        premium=0.07,
    )),
)


OUT_OF_REGIME_SPEC = _with_stores(_spec(
    campaign="roller-pin-2027",
    draw=8642,
    mu_a=8.4,
    ratio=1.03,
    lots=[
        _lot("A-7301", "A", 34, [2] * 9),
        _lot("A-7309", "A", 44, [2] * 9),
        _lot("A-7316", "A", 52, [2] * 9, spares=1),
        _lot("A-7324", "A", 61, [2, 2, 1, 1, 2, 2, 2, 2, 2], spares=2),
        _lot("A-7332", "A", 72, [1] * 7, spares=1),
        _lot("A-7340", "A", 80, [2] * 6, spares=1),
        _lot("B-2501", "B", 3, [1] * 13),
        _lot("B-2512", "B", 12, [1] * 13),
        _lot("B-2523", "B", 21, [1] * 13, spares=1),
        _lot("B-2534", "B", 40, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2], spares=2),
        _lot("B-2545", "B", 66, [2] * 5, spares=1),
    ],
    calibration_days={1: [1, 39, 70], 2: [30, 48, 64]},
    beta={1: 0.0010, 2: 0.0030},
    fixture_ratio=0.93,
    rig2_installed_day=30,
    review_day=92,
    bench_hours_left=24.0,
    rig_hours_available={1: 24.0, 2: 10.0},
    premium=0.10,
))


def _variant(name: str, **changes: Any) -> dict[str, Any]:
    'The campaign in hand with the bench schedule re-run another way.'

    spec = {key: value for key, value in CURRENT_SPEC.items()}
    spec["campaign"] = name
    for key, value in changes.items():
        spec[key] = value
    return spec


_REASSIGNED_ONE = [
    _lot("A-3308", "A", 3, [1] * 9, spares=1),
    _lot("A-3312", "A", 9, [1] * 9),
    _lot("A-3317", "A", 15, [1] * 9),
    _lot("A-3321", "A", 22, [1] * 9, spares=1),
    _lot("A-3330", "A", 40, [1, 1, 1, 1, 1, 2, 2, 2], spares=3),
    _lot("A-3336", "A", 68, [1, 2, 2, 2], spares=1),
    _lot("B-7101", "B", 33, [2] * 9),
    _lot("B-7108", "B", 44, [2] * 9),
    _lot("B-7115", "B", 52, [1, 1, 1, 2, 2, 2, 2, 2, 2], spares=1),
    _lot("B-7122", "B", 62, [1, 1, 1, 1, 2, 2, 2, 2, 2, 2], spares=3),
    _lot("B-7130", "B", 74, [1, 1, 1, 1, 1, 1, 2, 2, 2], spares=1),
]

_REASSIGNED_TWO = [
    _lot("A-3308", "A", 3, [1] * 9, spares=1),
    _lot("A-3312", "A", 9, [1] * 9),
    _lot("A-3317", "A", 15, [1] * 9),
    _lot("A-3321", "A", 22, [1] * 9, spares=1),
    _lot("A-3330", "A", 40, [1, 1, 1, 1, 1, 1, 2, 2], spares=3),
    _lot("A-3336", "A", 68, [2, 2, 1, 1], spares=1),
    _lot("B-7101", "B", 33, [2] * 9),
    _lot("B-7108", "B", 44, [1, 1, 1, 2, 2, 2, 2, 2, 2]),
    _lot("B-7115", "B", 52, [2] * 9, spares=1),
    _lot("B-7122", "B", 62, [1, 1, 2, 2, 2, 2, 2, 2, 2, 2], spares=3),
    _lot("B-7130", "B", 74, [1, 1, 1, 1, 2, 2, 2, 2, 2], spares=1),
]


INVARIANCE_SPECS: Mapping[str, tuple[dict[str, Any], ...]] = {
    "drift_rate": (
        _variant("bushing-slow-bench", beta={1: 0.0008, 2: 0.0003}),
        _variant("bushing-fast-bench", beta={1: 0.0050, 2: 0.0026}),
    ),
    "assignment": (
        _with_stores(_variant("bushing-rigs-shared", lots=_REASSIGNED_ONE)),
        _with_stores(_variant("bushing-rigs-swapped", lots=_REASSIGNED_TWO)),
    ),
    "calibration_spacing": (
        _variant("bushing-short-intervals",
                 calibration_days={1: [1, 16, 28, 40, 52, 62, 73], 2: [30, 36, 42, 48, 54, 62, 70]}),
        _variant("bushing-long-intervals",
                 calibration_days={1: [1], 2: [30]}),
    ),
}

SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)
OUT_OF_REGIME = build(OUT_OF_REGIME_SPEC)
INVARIANCE = {
    reason: tuple(build(spec) for spec in specs)
    for reason, specs in INVARIANCE_SPECS.items()
}


REPORT_PROBE_SPECS = (
    _variant("bushing-qualification-2027-1", draw=9004, ratio=0.82),
    _variant("bushing-qualification-2027-2", draw=9004, ratio=1.18),
    _variant(
        "bushing-qualification-2027-3",
        draw=9004,
        lot_sd=0.04,
        part_sd=0.015,
        noise_sd=0.05,
    ),
    _variant(
        "bushing-qualification-2027-4",
        draw=9004,
        lot_sd=0.28,
        part_sd=0.04,
        noise_sd=0.16,
    ),
)

REPORT_PROBES = tuple(build(spec) for spec in REPORT_PROBE_SPECS)
