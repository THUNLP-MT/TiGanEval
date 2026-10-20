'The sweep under study, the sweeps the same notebook is used on next, and the paired draws that hold one surface fixed while the machinery around it changes.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .world import build


TRAINING_BLOCKS = ("web-crawl-a", "web-crawl-b", "code-2025", "forum-threads")
RESERVED_BLOCKS = (
    "news-2025",
    "books-1",
    "wiki-core",
    "reviews-2024",
    "news-2026",
    "books-2",
    "wiki-talk",
)

LINEAGES = {
    "val-a": "news-2025",
    "val-b": "books-1",
    "val-c": "wiki-core",
    "val-d": "reviews-2024",
    "val-e": "news-2026",
    "val-f": "books-2",
    "val-g": "wiki-talk",
    "val-h": "forum-threads",
}


def _blocks() -> list[dict[str, str]]:
    rows = [{"block": name, "role": "training mixture"} for name in TRAINING_BLOCKS]
    rows.extend(
        {"block": name, "role": "reserved"}
        for name in RESERVED_BLOCKS
        if name not in set(TRAINING_BLOCKS)
    )
    return sorted(rows, key=lambda row: row["block"])


def _shards(offsets: Mapping[str, float]) -> dict[str, Any]:
    return {
        shard: {"offset": float(offsets[shard]), "lineage": LINEAGES[shard]}
        for shard in sorted(offsets)
    }


def _run(run_id, date, width, data, rate, shard, loader="v2") -> dict[str, Any]:
    return {
        "run_id": run_id,
        "date": date,
        "width": width,
        "data": data,
        "learning_rate": rate,
        "val_shard_id": shard,
        "loader_version": loader,
    }


def _spec(
    sweep: str,
    *,
    noise_key: str | None = None,
    floor: float,
    A: float,
    a: float,
    B: float,
    b: float,
    noise_sd: float,
    contamination: float,
    rate_onset: float,
    unstable_width: int,
    late_shortfall: tuple[float, float],
    late_rise: tuple[float, float],
    offsets: Mapping[str, float],
    runs: Sequence[Mapping[str, Any]],
    units_granted: int,
    reservation_days: int,
    changes: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    return {
        "sweep": sweep,
        "noise_key": str(noise_key or sweep),
        "floor": floor,
        "A": A,
        "a": a,
        "B": B,
        "b": b,
        "noise_sd": noise_sd,
        "contamination": contamination,
        "rate_onset": rate_onset,
        "unstable_width": unstable_width,
        "late_shortfall": tuple(late_shortfall),
        "late_rise": tuple(late_rise),
        "blocks": _blocks(),
        "shards": _shards(offsets),
        "runs": [dict(run) for run in runs],
        "unit_divisor": 1_750_000,
        "units_granted": units_granted,
        "job_cap_units": 12000,
        "job_floor_units": 2500,
        "reservation_days": reservation_days,
        "target_multiple": 10,
        "changes": [dict(entry) for entry in changes],
    }


def _reshard(
    runs: Sequence[Mapping[str, Any]], moves: Mapping[str, str]
) -> tuple[dict[str, Any], ...]:
    return tuple(
        dict(run, val_shard_id=moves.get(str(run["run_id"]), run["val_shard_id"]))
        for run in runs
    )


ATHENA_OFFSETS = {
    "val-a": 0.014,
    "val-b": -0.009,
    "val-c": 0.021,
    "val-d": -0.017,
    "val-e": 0.006,
    "val-f": -0.012,
    "val-g": 0.019,
    "val-h": 0.008,
}


ATHENA_RUNS = (
    _run("r-001", "2026-04-26", 24, 6000, 0.030, "val-a"),
    _run("r-002", "2026-04-27", 24, 10000, 0.030, "val-e"),
    _run("r-003", "2026-04-29", 32, 8000, 0.030, "val-b"),
    _run("r-004", "2026-05-01", 32, 14000, 0.030, "val-g"),
    _run("r-005", "2026-05-03", 48, 12000, 0.028, "val-c"),
    _run("r-006", "2026-05-05", 48, 20000, 0.028, "val-d"),
    _run("r-007", "2026-05-07", 64, 16000, 0.028, "val-f"),
    _run("r-008", "2026-05-09", 64, 28000, 0.028, "val-a"),
    _run("r-009", "2026-05-11", 96, 24000, 0.026, "val-c"),
    _run("r-010", "2026-05-13", 96, 40000, 0.026, "val-e"),
    _run("r-011", "2026-05-15", 96, 24000, 0.026, "val-d"),
    _run("r-012", "2026-05-17", 128, 32000, 0.026, "val-b"),
    _run("r-013", "2026-05-19", 128, 52000, 0.024, "val-f"),
    _run("r-014", "2026-05-21", 160, 40000, 0.024, "val-g"),
    _run("r-015", "2026-05-23", 160, 68000, 0.024, "val-a"),
    _run("r-016", "2026-05-25", 192, 48000, 0.022, "val-g"),
    _run("r-017", "2026-05-27", 192, 80000, 0.022, "val-e"),
    _run("r-018", "2026-05-29", 192, 48000, 0.022, "val-f"),
    _run("r-019", "2026-05-31", 256, 64000, 0.056, "val-b"),
    _run("r-020", "2026-06-02", 256, 100000, 0.048, "val-c"),
    _run("r-021", "2026-06-06", 320, 80000, 0.058, "val-d", "v3"),
    _run("r-022", "2026-06-09", 320, 130000, 0.060, "val-a", "v3"),
    _run("r-023", "2026-06-13", 384, 96000, 0.020, "val-h", "v3"),
    _run("r-024", "2026-06-17", 384, 120000, 0.020, "val-h", "v3"),
)

ATHENA_CHANGES = (
    {
        "day": "2026-04-26",
        "kind": "sweep_open",
        "note": "Sweep opened on the shared queue; jobs run on whichever machines come free.",
    },
    {
        "day": "2026-05-12",
        "kind": "queue_cap",
        "note": "Per-job cap held at 12000 units; two reservations over it were killed at submission.",
    },
    {
        "day": "2026-06-05",
        "kind": "loader",
        "note": "Loader v3 rolled out on day 41. It resolves a validation shard index against the pooled block list; v2 resolved it against the reserved block list.",
    },
    {
        "day": "2026-06-17",
        "kind": "sweep_close",
        "note": "Last reservation of the sweep ran; the summary table was frozen the same evening.",
    },
    {
        "day": "2026-06-20",
        "kind": "queue_terms",
        "note": "Shared queue moved to reservation blocks: the 12000-unit cap is unchanged and it now refuses anything charged under 2500 units.",
    },
)

ATHENA_SPEC = _spec(
    "athena-summer",
    floor=1.05,
    A=3.2,
    a=0.36,
    B=8.2,
    b=0.31,
    noise_sd=0.008,
    contamination=-0.060,
    rate_onset=0.0505,
    unstable_width=256,
    late_shortfall=(0.06, 0.12),
    late_rise=(0.06, 0.13),
    offsets=ATHENA_OFFSETS,
    runs=ATHENA_RUNS,
    units_granted=26000,
    reservation_days=9,
    changes=ATHENA_CHANGES,
)


BOREALIS_OFFSETS = {
    "val-a": -0.011,
    "val-b": 0.018,
    "val-c": -0.020,
    "val-d": 0.013,
    "val-e": -0.006,
    "val-f": 0.022,
    "val-g": -0.015,
    "val-h": -0.004,
}

BOREALIS_RUNS = (
    _run("b-001", "2026-02-09", 32, 7000, 0.032, "val-c"),
    _run("b-002", "2026-02-11", 32, 13000, 0.032, "val-f"),
    _run("b-003", "2026-02-13", 48, 11000, 0.030, "val-a"),
    _run("b-004", "2026-02-15", 48, 21000, 0.030, "val-e"),
    _run("b-005", "2026-02-17", 64, 15000, 0.030, "val-b"),
    _run("b-006", "2026-02-19", 64, 27000, 0.030, "val-g"),
    _run("b-007", "2026-02-21", 96, 22000, 0.028, "val-d"),
    _run("b-008", "2026-02-23", 96, 22000, 0.028, "val-a"),
    _run("b-009", "2026-02-25", 96, 45000, 0.028, "val-c"),
    _run("b-010", "2026-02-27", 128, 30000, 0.026, "val-e"),
    _run("b-011", "2026-03-01", 128, 58000, 0.026, "val-b"),
    _run("b-012", "2026-03-03", 160, 38000, 0.026, "val-f"),
    _run("b-013", "2026-03-06", 160, 72000, 0.024, "val-h", "v3"),
    _run("b-014", "2026-03-08", 192, 46000, 0.024, "val-h", "v3"),
    _run("b-015", "2026-03-10", 192, 90000, 0.024, "val-g", "v3"),
    _run("b-016", "2026-03-12", 224, 54000, 0.050, "val-c", "v3"),
    _run("b-017", "2026-03-14", 224, 105000, 0.022, "val-d", "v3"),
    _run("b-018", "2026-03-16", 256, 62000, 0.022, "val-a", "v3"),
    _run("b-019", "2026-03-18", 288, 140000, 0.020, "val-e", "v3"),
    _run("b-020", "2026-03-20", 288, 70000, 0.048, "val-f", "v3"),
    _run("b-021", "2026-03-22", 352, 88000, 0.020, "val-b", "v3"),
    _run("b-022", "2026-03-25", 448, 90000, 0.018, "val-g", "v3"),
)

BOREALIS_CHANGES = (
    {
        "day": "2026-02-09",
        "kind": "sweep_open",
        "note": "Sweep opened on the shared queue; jobs run on whichever machines come free.",
    },
    {
        "day": "2026-03-05",
        "kind": "loader",
        "note": "Loader v3 rolled out on day 25. It resolves a validation shard index against the pooled block list; v2 resolved it against the reserved block list.",
    },
    {
        "day": "2026-03-25",
        "kind": "sweep_close",
        "note": "Last reservation of the sweep ran; the summary table was frozen that afternoon.",
    },
    {
        "day": "2026-06-20",
        "kind": "queue_terms",
        "note": "Shared queue moved to reservation blocks: the 12000-unit cap is unchanged and it now refuses anything charged under 2500 units.",
    },
)

BOREALIS_SPEC = _spec(
    "borealis-spring",
    floor=0.96,
    A=4.1,
    a=0.33,
    B=6.4,
    b=0.34,
    noise_sd=0.009,
    contamination=-0.072,
    rate_onset=0.042,
    unstable_width=224,
    late_shortfall=(0.05, 0.11),
    late_rise=(0.07, 0.15),
    offsets=BOREALIS_OFFSETS,
    runs=BOREALIS_RUNS,
    units_granted=31000,
    reservation_days=7,
    changes=BOREALIS_CHANGES,
)

CIRRUS_OFFSETS = {
    "val-a": 0.009,
    "val-b": -0.014,
    "val-c": 0.017,
    "val-d": -0.021,
    "val-e": 0.011,
    "val-f": -0.008,
    "val-g": 0.023,
    "val-h": -0.005,
}


CIRRUS_RUNS = (
    _run("c-001", "2025-11-04", 24, 6000, 0.030, "val-b"),
    _run("c-002", "2025-11-06", 32, 8000, 0.030, "val-e"),
    _run("c-003", "2025-11-08", 40, 10000, 0.030, "val-a"),
    _run("c-004", "2025-11-10", 48, 12000, 0.028, "val-g"),
    _run("c-005", "2025-11-12", 56, 14000, 0.028, "val-c"),
    _run("c-006", "2025-11-14", 64, 16000, 0.028, "val-f"),
    _run("c-007", "2025-11-16", 80, 20000, 0.026, "val-d"),
    _run("c-008", "2025-11-18", 96, 24000, 0.026, "val-b"),
    _run("c-009", "2025-11-20", 96, 24000, 0.026, "val-g"),
    _run("c-010", "2025-11-22", 112, 28000, 0.026, "val-e"),
    _run("c-011", "2025-11-24", 128, 32000, 0.024, "val-a"),
    _run("c-012", "2025-11-26", 144, 36000, 0.024, "val-c"),
    _run("c-013", "2025-11-28", 160, 40000, 0.024, "val-f"),
    _run("c-014", "2025-11-30", 176, 44000, 0.022, "val-d"),
    _run("c-015", "2025-12-02", 192, 48000, 0.022, "val-b"),
    _run("c-016", "2025-12-04", 224, 130000, 0.020, "val-e"),
    _run("c-017", "2025-12-06", 256, 40000, 0.020, "val-a"),
    _run("c-018", "2025-12-08", 256, 150000, 0.055, "val-c"),
    _run("c-019", "2025-12-11", 288, 45000, 0.018, "val-h", "v3"),
    _run("c-020", "2025-12-13", 320, 180000, 0.018, "val-h", "v3"),
    _run("c-021", "2025-12-15", 352, 55000, 0.018, "val-g", "v3"),
    _run("c-022", "2025-12-17", 384, 90000, 0.016, "val-h", "v3"),
)

CIRRUS_CHANGES = (
    {
        "day": "2025-11-04",
        "kind": "sweep_open",
        "note": "Sweep opened on the shared queue; jobs run on whichever machines come free.",
    },
    {
        "day": "2025-12-10",
        "kind": "loader",
        "note": "Loader v3 rolled out on day 37. It resolves a validation shard index against the pooled block list; v2 resolved it against the reserved block list.",
    },
    {
        "day": "2025-12-17",
        "kind": "sweep_close",
        "note": "Last reservation of the sweep ran; the summary table was frozen the next morning.",
    },
    {
        "day": "2026-06-20",
        "kind": "queue_terms",
        "note": "Shared queue moved to reservation blocks: the 12000-unit cap is unchanged and it now refuses anything charged under 2500 units.",
    },
)

CIRRUS_SPEC = _spec(
    "cirrus-winter",
    floor=1.18,
    A=2.7,
    a=0.40,
    B=9.5,
    b=0.28,
    noise_sd=0.007,
    contamination=-0.068,
    rate_onset=0.045,
    unstable_width=224,
    late_shortfall=(0.05, 0.10),
    late_rise=(0.06, 0.12),
    offsets=CIRRUS_OFFSETS,
    runs=CIRRUS_RUNS,
    units_granted=18000,
    reservation_days=6,
    changes=CIRRUS_CHANGES,
)


ATHENA_CLEAN_SPEC = _spec(
    "hyperion-autumn",
    noise_key="athena-summer",
    floor=1.05,
    A=3.2,
    a=0.36,
    B=8.2,
    b=0.31,
    noise_sd=0.008,
    contamination=-0.060,
    rate_onset=0.0505,
    unstable_width=256,
    late_shortfall=(0.06, 0.12),
    late_rise=(0.06, 0.13),
    offsets=ATHENA_OFFSETS,
    runs=tuple(
        dict(
            run,
            val_shard_id={"r-023": "val-g", "r-024": "val-c"}.get(
                str(run["run_id"]), run["val_shard_id"]
            ),
            learning_rate={"r-019": 0.026, "r-021": 0.024, "r-022": 0.022}.get(
                str(run["run_id"]), run["learning_rate"]
            ),
        )
        for run in ATHENA_RUNS
    ),
    units_granted=26000,
    reservation_days=9,
    changes=ATHENA_CHANGES,
)


ATHENA_OTHER_SHARDS_SPEC = _spec(
    "iolite-july",
    noise_key="athena-summer",
    floor=1.05,
    A=3.2,
    a=0.36,
    B=8.2,
    b=0.31,
    noise_sd=0.008,
    contamination=-0.081,
    rate_onset=0.0505,
    unstable_width=256,
    late_shortfall=(0.06, 0.12),
    late_rise=(0.06, 0.13),
    offsets={
        "val-a": -0.018,
        "val-b": -0.006,
        "val-c": 0.022,
        "val-d": -0.011,
        "val-e": 0.009,
        "val-f": 0.013,
        "val-g": 0.004,
        "val-h": 0.017,
    },
    runs=_reshard(
        ATHENA_RUNS,
        {"r-015": "val-h", "r-017": "val-h", "r-023": "val-g", "r-024": "val-c"},
    ),
    units_granted=26000,
    reservation_days=9,
    changes=ATHENA_CHANGES,
)


BOREALIS_STEADY_SPEC = _spec(
    "janus-april",
    noise_key="borealis-spring",
    floor=0.96,
    A=4.1,
    a=0.33,
    B=6.4,
    b=0.34,
    noise_sd=0.009,
    contamination=-0.072,
    rate_onset=0.098,
    unstable_width=224,
    late_shortfall=(0.05, 0.11),
    late_rise=(0.07, 0.15),
    offsets=BOREALIS_OFFSETS,
    runs=BOREALIS_RUNS,
    units_granted=31000,
    reservation_days=7,
    changes=BOREALIS_CHANGES,
)


CURRENT = build(ATHENA_SPEC)
FOLLOWING = (build(BOREALIS_SPEC), build(CIRRUS_SPEC))


PAIRS = (
    (CURRENT, build(ATHENA_CLEAN_SPEC), "shifts_when_nothing_was_set_aside"),
    (CURRENT, build(ATHENA_OTHER_SHARDS_SPEC), "shifts_with_the_shard_offsets"),
    (FOLLOWING[0], build(BOREALIS_STEADY_SPEC), "shifts_with_the_rate_that_comes_apart"),
)


INSTANCES = (CURRENT, *FOLLOWING, *(variant for _base, variant, _mode in PAIRS))
