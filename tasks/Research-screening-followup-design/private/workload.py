'The screen under review, and the screens the same notebook is run on next.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import bench
from .world import COUPON, INCUMBENT, build


def _spec(**fields: Any) -> dict[str, Any]:
    spec = dict(fields)
    spec.setdefault("operators", ("Ivo Brandt", "Marta Reiner", "Suli Rahman"))
    spec.setdefault("screen_runs", 2)


    spec.setdefault("runs_per_day", 4)
    spec.setdefault("fixture_changes_per_day", 2)
    spec.setdefault("rig_hours_per_day", "9")
    return spec


def _log(rows: Sequence[tuple[str, str, str, str]]) -> dict[str, dict[str, str]]:
    return {
        day: {"coolant_setpoint_C": setpoint, "ambient_C": ambient, "note": note}
        for day, setpoint, ambient, note in rows
    }


JULY = _spec(
    campaign="hs-july",
    label="July spreader screen",
    incumbent_rise="18.0",
    stored_baseline_rise="18.4",
    baseline_day="2026-05-11",
    plates={
        "P-01": "0.10",
        "P-02": "-0.35",
        "P-03": "0.05",
        "P-04": "0.35",
        "P-05": "-0.10",
        "P-06": "0.50",
        "P-07": "1.20",
        "P-08": "0.05",
        "P-09": "0.45",
        "P-10": "0.05",
        "P-11": "0.25",
        "P-12": "0.25",
    },
    coupon_truth="0.40",
    selected_plate="P-07",
    screen_days=("2026-07-06", "2026-07-07", "2026-07-13", "2026-07-14"),
    assignment={
        "2026-07-06": ("P-01", "P-05", "P-09"),
        "2026-07-07": ("P-02", "P-06", "P-10"),
        "2026-07-13": ("P-03", "P-07", "P-11"),
        "2026-07-14": ("P-04", "P-08", "P-12"),
    },
    alternate_assignment={
        "2026-07-06": ("P-03", "P-07", "P-11"),
        "2026-07-07": ("P-04", "P-08", "P-12"),
        "2026-07-13": ("P-01", "P-05", "P-09"),
        "2026-07-14": ("P-02", "P-06", "P-10"),
    },
    coupon_days=("2026-07-07", "2026-07-14"),
    open_days=(
        "2026-09-03",
        "2026-09-04",
        "2026-09-09",
        "2026-09-10",
        "2026-09-11",
    ),
    day_shift={
        "2026-07-06": "0.70",
        "2026-07-07": "-0.15",
        "2026-07-13": "-0.45",
        "2026-07-14": "0.85",
        "2026-09-03": "0.30",
        "2026-09-04": "-0.55",
        "2026-09-09": "0.25",
        "2026-09-10": "-0.60",
        "2026-09-11": "0.40",
    },
    alternate_shift={
        "2026-07-06": "-0.35",
        "2026-07-07": "0.60",
        "2026-07-13": "0.55",
        "2026-07-14": "-0.20",
        "2026-09-03": "0.10",
        "2026-09-04": "0.20",
        "2026-09-09": "-0.15",
        "2026-09-10": "0.45",
        "2026-09-11": "-0.30",
    },
    rig_log=_log(
        (
            ("2026-07-06", "19.5", "23.1", "Screen block 1. Bay fan on the low tap all day."),
            ("2026-07-07", "19.6", "22.9", "Screen block 2. Reference plate run in the last slot."),
            ("2026-07-13", "19.1", "23.4", "Screen block 3. Chiller back from service on the 9th."),
            ("2026-07-14", "19.3", "22.6", "Screen block 4. Reference plate run in the last slot."),
            ("2026-09-03", "19.4", "23.2", "Day booked for the review; sheet handed back at the desk."),
            ("2026-09-04", "18.9", "22.3", "Confirming runs on the selected plate."),
            ("2026-09-09", "19.2", "22.8", "Held for the review."),
            ("2026-09-10", "18.8", "22.5", "Held for the review."),
            ("2026-09-11", "19.5", "23.0", "Held for the review."),
        )
    ),
    run_spread="0.50",
    run_scatter="0.26",
    seating_spread="0.17",
    day_shift_sd="0.60",
    rig_days_on_the_sheet=5,
    range_width_K="0.85",
    review_due="2026-09-15",
)


STARTING_SHEETS: tuple[tuple[dict[str, Any], ...], ...] = (
    (
        {"part": "P-07", "runs": 2},
        {"part": "P-06", "runs": 1},
        {"part": "P-03", "runs": 1},
    ),
    ({"part": "P-07", "runs": 4},),
)
STARTING_IDS = ("mr-0903", "mr-0904")


AUGUST = _spec(
    campaign="mount-ring-august",
    label="August mount-ring screen",
    incumbent_rise="21.0",
    stored_baseline_rise="21.6",
    baseline_day="2026-06-02",
    plates={
        "M-01": "0.20",
        "M-02": "-0.15",
        "M-03": "0.60",
        "M-04": "0.05",
        "M-05": "0.35",
        "M-06": "0.90",
        "M-07": "-0.20",
        "M-08": "0.15",
        "M-09": "0.45",
        "M-10": "0.00",
    },
    coupon_truth="0.30",
    selected_plate="M-06",
    screen_days=("2026-08-03", "2026-08-04", "2026-08-10", "2026-08-11"),
    assignment={
        "2026-08-03": ("M-01", "M-02", "M-03"),
        "2026-08-04": ("M-04", "M-05", "M-06"),
        "2026-08-10": ("M-07", "M-08"),
        "2026-08-11": ("M-09", "M-10"),
    },
    alternate_assignment={
        "2026-08-03": ("M-04", "M-05", "M-06"),
        "2026-08-04": ("M-01", "M-02", "M-03"),
        "2026-08-10": ("M-09", "M-10"),
        "2026-08-11": ("M-07", "M-08"),
    },
    coupon_days=("2026-08-03", "2026-08-10"),


    open_days=("2026-09-14", "2026-09-16", "2026-09-17"),
    day_shift={
        "2026-08-03": "0.20",
        "2026-08-04": "-0.35",
        "2026-08-10": "0.75",
        "2026-08-11": "0.10",
        "2026-09-14": "0.35",
        "2026-09-16": "-0.25",
        "2026-09-17": "0.15",
    },
    alternate_shift={
        "2026-08-03": "-0.40",
        "2026-08-04": "0.30",
        "2026-08-10": "-0.10",
        "2026-08-11": "0.65",
        "2026-09-14": "-0.10",
        "2026-09-16": "0.40",
        "2026-09-17": "-0.30",
    },
    rig_log=_log(
        (
            ("2026-08-03", "19.4", "23.0", "Screen block 1. Reference plate in the last slot."),
            ("2026-08-04", "19.7", "22.4", "Screen block 2."),
            ("2026-08-10", "19.0", "23.5", "Screen block 3. Reference plate in the last slot."),
            ("2026-08-11", "19.3", "22.7", "Screen block 4."),
            ("2026-09-14", "19.2", "22.6", "Held for the review."),
            ("2026-09-16", "19.4", "23.0", "Held for the review."),
            ("2026-09-17", "19.1", "22.5", "Held for the review."),
        )
    ),
    run_spread="0.58",
    run_scatter="0.30",
    seating_spread="0.09",
    day_shift_sd="0.46",
    rig_days_on_the_sheet=3,
    range_width_K="0.90",
    review_due="2026-09-22",
)

SEPTEMBER = _spec(
    campaign="sink-fin-september",
    label="September fin screen",
    incumbent_rise="15.5",
    stored_baseline_rise="15.9",
    baseline_day="2026-07-01",
    plates={
        "S-01": "0.15",
        "S-02": "0.40",
        "S-03": "-0.05",
        "S-04": "0.55",
        "S-05": "0.25",
        "S-06": "-0.30",
        "S-07": "0.10",
        "S-08": "0.70",
        "S-09": "0.20",
        "S-10": "0.00",
        "S-11": "0.35",
        "S-12": "0.05",
        "S-13": "0.95",
        "S-14": "0.30",
    },
    coupon_truth="0.25",
    selected_plate="S-13",
    screen_days=("2026-09-01", "2026-09-02", "2026-09-07", "2026-09-08"),
    assignment={
        "2026-09-01": ("S-01", "S-02", "S-03", "S-04"),
        "2026-09-02": ("S-05", "S-06", "S-07", "S-08"),
        "2026-09-07": ("S-09", "S-10", "S-11"),
        "2026-09-08": ("S-12", "S-13", "S-14"),
    },
    alternate_assignment={
        "2026-09-01": ("S-05", "S-06", "S-07", "S-08"),
        "2026-09-02": ("S-01", "S-02", "S-03", "S-04"),
        "2026-09-07": ("S-12", "S-13", "S-14"),
        "2026-09-08": ("S-09", "S-10", "S-11"),
    },
    coupon_days=("2026-09-02", "2026-09-08"),
    open_days=("2026-09-21", "2026-09-22", "2026-09-23"),
    day_shift={
        "2026-09-01": "0.05",
        "2026-09-02": "0.55",
        "2026-09-07": "0.15",
        "2026-09-08": "-0.50",
        "2026-09-21": "0.30",
        "2026-09-22": "-0.40",
        "2026-09-23": "0.15",
    },
    alternate_shift={
        "2026-09-01": "-0.30",
        "2026-09-02": "0.15",
        "2026-09-07": "0.60",
        "2026-09-08": "0.20",
        "2026-09-21": "-0.10",
        "2026-09-22": "0.35",
        "2026-09-23": "-0.25",
    },
    rig_log=_log(
        (
            ("2026-09-01", "19.3", "22.8", "Screen block 1."),
            ("2026-09-02", "19.6", "23.3", "Screen block 2. Reference plate in the last slot."),
            ("2026-09-07", "19.1", "22.5", "Screen block 3."),
            ("2026-09-08", "18.9", "22.9", "Screen block 4. Reference plate in the last slot."),
            ("2026-09-21", "19.4", "23.0", "Held for the review."),
            ("2026-09-22", "18.8", "22.4", "Held for the review."),
            ("2026-09-23", "19.2", "22.7", "Held for the review."),
        )
    ),
    run_spread="0.42",
    run_scatter="0.22",
    seating_spread="0.08",
    day_shift_sd="0.44",
    rig_days_on_the_sheet=3,
    range_width_K="0.60",
    review_due="2026-10-06",
)

CURRENT = build(JULY)
LATER = (build(AUGUST), build(SEPTEMBER))
ALL_CAMPAIGNS = (CURRENT, *LATER)


def paired_sheet(world: Any, runs: int = 2) -> list[dict[str, Any]]:
    'One day carrying the selected plate and the incumbent, `runs` each.'

    return [
        {"part": world.selected, "runs": int(runs)},
        {"part": INCUMBENT, "runs": int(runs)},
    ]


def starting_stream() -> dict[str, Any]:
    'The receipt stream the July review starts from: two days already charged.'

    return bench.stream(CURRENT, [list(sheet) for sheet in STARTING_SHEETS], STARTING_IDS)


def settled_stream(world: Any) -> dict[str, Any]:
    "A later screen's stream once its remaining rig days have been run paired."

    sheets = [paired_sheet(world) for _ in range(int(world.spec["rig_days_on_the_sheet"]))]
    ids = [f"{world.campaign}-{index}" for index in range(1, len(sheets) + 1)]
    return bench.stream(world, sheets, ids)


def campaign_of(name: str) -> Any:
    for world in ALL_CAMPAIGNS:
        if world.campaign == name:
            return world
    raise KeyError(name)


PARTS: Mapping[str, str] = {"incumbent": INCUMBENT, "reference": COUPON}
