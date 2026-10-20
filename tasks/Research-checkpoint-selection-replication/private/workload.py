'The campaign under review, and the campaigns the same notebook is run over.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import world


CHECKPOINT_STEPS = tuple(range(500, 22501, 500))


def _run(
    run_id: str,
    init_id: str,
    warmup: str,
    ceiling: float,
    amplitude: float,
    tau: int,
    group: int,
    trainer_version: str,
    loss_offset: float,
    turn_rate: float = 0.0,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "init_id": init_id,
        "warmup": warmup,
        "ceiling": float(ceiling),
        "amplitude": float(amplitude),
        "tau": int(tau),
        "group": int(group),
        "trainer_version": trainer_version,
        "loss_offset": float(loss_offset),
        "turn_rate": float(turn_rate),
        "compute_units": 520,
    }


def _retained(runs: Sequence[Mapping[str, Any]], pinned: Sequence[str]) -> tuple[str, ...]:
    'The checkpoints the retention job removed from disk.'

    keep = set(pinned)
    pruned = []
    for entry in runs:
        for step in CHECKPOINT_STEPS:
            item = f"{entry['run_id']}@{step}"
            if item in keep or step % 2500 == 0 or step >= 18500:
                continue
            pruned.append(item)
    return tuple(pruned)


def _spec(**fields: Any) -> dict[str, Any]:
    "One campaign's parameters."

    spec = dict(fields)
    if not str(spec.get("owner_label", "")).strip():
        raise ValueError(f"{spec.get('campaign')} needs a name its owner would use")
    spec.setdefault("checkpoint_steps", CHECKPOINT_STEPS)
    spec.setdefault("slices", 8)
    spec.setdefault("slice_rows", 4100)
    spec.setdefault("slice_sd", 0.0063)
    spec.setdefault("read_sd", 0.0044)
    spec.setdefault("lot_sd", 0.0110)
    spec.setdefault("units_granted", 1030)
    spec.setdefault("reserve", 150)
    spec.setdefault("job_cap", 480)
    spec.setdefault("read_price", 30)
    spec.setdefault("train_price", 520)
    spec.setdefault("refusal_fee", 10)
    spec.setdefault("range_ask_points", 1.0)
    spec.setdefault("prune_date", "2026-08-21")
    spec["pruned"] = _retained(spec["runs"], spec.get("pinned", ()))
    return spec


CURRENT_RUNS = (
    _run("r01", "init-71c4", "standard", 0.8098, 0.118, 4400, 1, "2.7.1", 1.482),
    _run("r02", "init-4a09", "standard", 0.8131, 0.101, 3800, 1, "2.7.1", 1.436),
    _run("r03", "init-71c4", "long", 0.8118, 0.134, 5200, 1, "2.7.1", 1.517, 0.0060),
    _run("r04", "init-9d52", "standard", 0.8087, 0.126, 4100, 1, "2.7.1", 1.461),
    _run("r05", "init-4a09", "standard", 0.8112, 0.113, 4700, 2, "2.7.1", 1.408),
    _run("r06", "init-2e88", "standard", 0.8113, 0.145, 3600, 2, "2.7.1", 1.529),
    _run("r07", "init-9d52", "long", 0.8106, 0.130, 4000, 2, "2.8.0", 1.394, 0.0090),
    _run("r08", "init-2e88", "standard", 0.8094, 0.094, 5900, 2, "2.8.0", 1.503),
)

CURRENT_SPEC = _spec(
    campaign="rank-2026-08",
    label="August marketplace-search ranking campaign",
    owner_label="the August ranking campaign",
    as_of="2026-09-04",
    runs=CURRENT_RUNS,
    pinned=("r06@13500", "r05@16500", "r02@14500"),
    groups={1: "v-2f9c", 2: "v-8b41"},
    swapped_groups={1: "v-8b41", 2: "v-2f9c"},
    lot_amount={"v-2f9c": 0.0, "v-8b41": 0.0164, "v-1c07": -0.0071},
    open_lots=("v-2f9c", "v-8b41"),
    retired_lots=("v-1c07",),
    turn_steps={"r03": 15000, "r07": 18500},
    moved_turn_steps={"r03": 10500, "r07": 13500},
    production={
        "model_id": "pr-rank-2024q4",
        "quality": 0.7902,
        "release_lot": "v-1c07",
        "release_slice": 0,
        "release_date": "2026-03-19",
    },
    review_due="2026-09-11",
)


STARTING_JOBS = (
    ("nb-0827", "reads", "v-8b41", ("r06@13500", "r05@13000", "r08@21000"), 2),
    ("nb-0901", "reads", "v-8b41", ("r06@13500", "r05@16500"), 2),
)


def _later_runs(
    ceilings: Sequence[float],
    amplitudes: Sequence[float],
    taus: Sequence[int],
    split: int,
    long_runs: Sequence[str],
    version_from: int,
    inits: Sequence[str],
    rates: Mapping[str, float],
) -> tuple[dict[str, Any], ...]:
    runs = []
    for index, ceiling in enumerate(ceilings, start=1):
        run_id = f"r{index:02d}"
        runs.append(
            _run(
                run_id,
                inits[(index - 1) % len(inits)],
                "long" if run_id in long_runs else "standard",
                ceiling,
                amplitudes[(index - 1) % len(amplitudes)],
                taus[(index - 1) % len(taus)],
                1 if index <= split else 2,
                "2.7.1" if index < version_from else "2.8.0",
                1.38 + 0.017 * index,
                rates.get(run_id, 0.0),
            )
        )
    return tuple(runs)


SEPTEMBER_SPEC = _spec(
    campaign="rank-2026-09",
    label="September marketplace-search re-rank",
    owner_label="the September re-rank",
    as_of="2026-09-30",
    runs=_later_runs(
        (0.8231, 0.8194, 0.8248, 0.8209, 0.8177, 0.8222, 0.8203),
        (0.108, 0.131, 0.096, 0.142, 0.119, 0.104, 0.126),
        (4900, 3700, 5600, 4200, 5100, 3900, 4500),
        3,
        ("r05",),
        6,
        ("init-3f10", "init-8b77", "init-c204"),
        {"r05": 0.0068},
    ),
    pinned=("r03@14500", "r06@16000"),
    groups={1: "v-8b41", 2: "v-51ad"},
    swapped_groups={1: "v-51ad", 2: "v-8b41"},
    lot_amount={"v-8b41": 0.0041, "v-51ad": 0.0186, "v-1c07": -0.0071},
    open_lots=("v-8b41", "v-51ad"),
    retired_lots=("v-1c07",),
    turn_steps={"r05": 16000},
    moved_turn_steps={"r05": 11000},
    production={
        "model_id": "pr-rank-2026q3",
        "quality": 0.7981,
        "release_lot": "v-8b41",
        "release_slice": 5,
        "release_date": "2026-09-08",
    },
    slice_rows=3600,
    slice_sd=0.0071,
    read_sd=0.0039,
    units_granted=1000,
    review_due="2026-10-09",
)

SUGGEST_SPEC = _spec(
    campaign="suggest-2026-08",
    label="August query-suggestion campaign",
    owner_label="the query-suggestion campaign",
    as_of="2026-09-02",
    runs=_later_runs(
        (0.6642, 0.6688, 0.6613, 0.6671, 0.6659, 0.6701, 0.6627, 0.6684),
        (0.087, 0.112, 0.098, 0.124, 0.091, 0.135, 0.104, 0.117),
        (3600, 4800, 5400, 4100, 3900, 5900, 4400, 5000),
        5,
        ("r02", "r08"),
        7,
        ("init-a51b", "init-d70e"),
        {"r02": 0.0051, "r08": 0.0079},
    ),
    pinned=("r06@13500",),
    groups={1: "v-6d3c", 2: "v-9f02"},
    swapped_groups={1: "v-9f02", 2: "v-6d3c"},
    lot_amount={"v-6d3c": 0.0128, "v-9f02": -0.0034, "v-4e88": 0.0057},
    open_lots=("v-6d3c", "v-9f02"),
    retired_lots=("v-4e88",),
    turn_steps={"r02": 14000, "r08": 17000},
    moved_turn_steps={"r02": 9500, "r08": 12000},
    production={
        "model_id": "pr-suggest-2025q2",
        "quality": 0.6489,
        "release_lot": "v-4e88",
        "release_slice": 2,
        "release_date": "2026-04-14",
    },
    slice_rows=4800,
    slice_sd=0.0058,
    read_sd=0.0047,
    units_granted=990,
    review_due="2026-09-18",
)

ADS_SPEC = _spec(
    campaign="ads-2026-07",
    label="July sponsored-placement campaign",
    owner_label="the sponsored-placement campaign",
    as_of="2026-08-28",
    runs=_later_runs(
        (0.7458, 0.7411, 0.7482, 0.7429, 0.7466, 0.7437),
        (0.121, 0.094, 0.137, 0.108, 0.115, 0.129),
        (4300, 5700, 3800, 4900, 5200, 4000),
        3,
        ("r04",),
        5,
        ("init-b0c9", "init-e42a", "init-77fd"),
        {"r04": 0.0064},
    ),
    pinned=("r03@15500",),
    groups={1: "v-2f9c", 2: "v-b710"},
    swapped_groups={1: "v-b710", 2: "v-2f9c"},
    lot_amount={"v-2f9c": -0.0062, "v-b710": 0.0094, "v-0aa4": 0.0031},
    open_lots=("v-2f9c", "v-b710"),
    retired_lots=("v-0aa4",),
    turn_steps={"r04": 13500},
    moved_turn_steps={"r04": 18500},
    production={
        "model_id": "pr-ads-2025q4",
        "quality": 0.7301,
        "release_lot": "v-0aa4",
        "release_slice": 6,
        "release_date": "2026-02-26",
    },
    slice_rows=3300,
    slice_sd=0.0066,

    read_sd=0.0039,
    units_granted=1090,
    review_due="2026-09-05",
)

FEED_SPEC = _spec(
    campaign="feed-2026-09",
    label="September home-feed campaign",
    owner_label="the home-feed campaign",
    as_of="2026-09-26",
    runs=_later_runs(
        (0.5893, 0.5941, 0.5917, 0.5878, 0.5926, 0.5904, 0.5933, 0.5886, 0.5911),
        (0.076, 0.103, 0.089, 0.118, 0.095, 0.127, 0.082, 0.111, 0.099),
        (5300, 4100, 4700, 3700, 5800, 4400, 3900, 5000, 4600),
        4,
        ("r06", "r09"),
        8,
        ("init-1d4f", "init-6c8b", "init-f339"),
        {"r06": 0.0057, "r09": 0.0083},
    ),
    pinned=("r02@17000",),
    groups={1: "v-33e1", 2: "v-8b41"},
    swapped_groups={1: "v-8b41", 2: "v-33e1"},
    lot_amount={"v-33e1": 0.0073, "v-8b41": -0.0089, "v-5c60": 0.0016},
    open_lots=("v-33e1", "v-8b41"),
    retired_lots=("v-5c60",),
    turn_steps={"r06": 15500, "r09": 11500},
    moved_turn_steps={"r06": 10000, "r09": 16500},
    production={
        "model_id": "pr-feed-2026q1",
        "quality": 0.5762,
        "release_lot": "v-5c60",
        "release_slice": 1,
        "release_date": "2026-05-07",
    },
    slice_rows=5200,
    slice_sd=0.0049,


    read_sd=0.0047,
    units_granted=1020,
    review_due="2026-10-02",
)

MERCH_SPEC = _spec(
    campaign="merch-2026-08",
    label="August merchandising campaign",
    owner_label="the merchandising campaign",
    as_of="2026-09-01",
    runs=_later_runs(
        (0.7024, 0.6987, 0.7041, 0.7009, 0.6996, 0.7033),
        (0.133, 0.101, 0.117, 0.092, 0.126, 0.108),
        (3500, 4600, 5500, 4200, 3800, 5100),
        4,
        ("r01",),
        6,
        ("init-9a2c", "init-40de"),
        {"r01": 0.0072},
    ),
    pinned=("r05@12000",),
    groups={1: "v-7c15", 2: "v-2f9c"},
    swapped_groups={1: "v-2f9c", 2: "v-7c15"},
    lot_amount={"v-7c15": -0.0021, "v-2f9c": 0.0139, "v-9911": -0.0048},
    open_lots=("v-7c15", "v-2f9c"),
    retired_lots=("v-9911",),
    turn_steps={"r01": 16500},
    moved_turn_steps={"r01": 12000},
    production={
        "model_id": "pr-merch-2025q3",
        "quality": 0.6871,
        "release_lot": "v-9911",
        "release_slice": 4,
        "release_date": "2026-03-05",
    },
    slice_rows=4400,
    slice_sd=0.0074,
    read_sd=0.0036,
    units_granted=1010,
    review_due="2026-09-09",
)


QUIET_SPEC = _spec(
    campaign="ranker-lab-quiet",
    label="Offline replication of the ranking campaign",
    owner_label="the offline replication",
    as_of="2026-09-03",
    runs=_later_runs(
        (0.8112, 0.8138, 0.8095, 0.8127, 0.8104, 0.8121),
        (0.111, 0.098, 0.124, 0.106, 0.117, 0.093),
        (4200, 3900, 5100, 4600, 4000, 5400),
        3,
        (),
        7,
        ("init-c001", "init-c002"),
        {},
    ),
    pinned=(),
    groups={1: "v-ff01", 2: "v-ff01"},
    swapped_groups={1: "v-ff01", 2: "v-ff01"},
    lot_amount={"v-ff01": 0.0034},
    open_lots=("v-ff01",),
    retired_lots=(),
    turn_steps={},
    moved_turn_steps={},
    production={
        "model_id": "pr-rank-lab",
        "quality": 0.7948,
        "release_lot": "v-ff01",
        "release_slice": 0,
        "release_date": "2026-08-30",
    },
    slice_rows=4000,
    slice_sd=0.0007,
    read_sd=0.0005,
    units_granted=1000,
    review_due="2026-09-12",
)


LATER_SPECS = (SEPTEMBER_SPEC, SUGGEST_SPEC, ADS_SPEC, FEED_SPEC, MERCH_SPEC)


_CACHE: dict[str, world.Campaign] = {}


def campaign(spec: Mapping[str, Any]) -> world.Campaign:
    key = str(spec["campaign"])
    if key not in _CACHE:
        _CACHE[key] = world.build(spec)
    return _CACHE[key]


def current() -> world.Campaign:
    return campaign(CURRENT_SPEC)


def later() -> tuple[world.Campaign, ...]:
    return tuple(campaign(spec) for spec in LATER_SPECS)


def quiet() -> world.Campaign:
    return campaign(QUIET_SPEC)


def every() -> tuple[world.Campaign, ...]:
    return (current(), *later(), quiet())


def starting_stream() -> list[dict[str, Any]]:
    'The receipt stream the release opens with.'

    campaign_under_review = current()
    entries: list[dict[str, Any]] = []
    for job_id, kind, lot, items, repeats in STARTING_JOBS:
        entries = world.extend(
            campaign_under_review, entries, job_id, kind, lot, items, repeats
        )
    return entries
