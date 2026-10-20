"""The five binary project checks for the bushing qualification."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "wear_rate_ratio": (
        "no_ratio_reported",
        "ratio_reported_in_raw_depth",
        "ratio_carries_uncorrected_drift",
        "ratio_takes_the_drift_off_as_a_fixed_amount",
        "ratio_carries_the_fixture_difference",
        "ratio_disagrees_with_the_bench",
        "ratio_does_not_hold_on_the_other_qualifications",
        EXECUTION_FAILURE_MODE,
    ),
    "correction_survives_the_bench_schedule": (
        "estimate_moves_with_drift_rate",
        "correction_keyed_to_rig_identity",
        "estimate_moves_with_assignment_imbalance",
        EXECUTION_FAILURE_MODE,
    ),
    "ratio_range_is_honest": (
        "no_range_reported",
        "range_is_not_an_interval",
        "range_does_not_hold_the_reported_ratio",
        "range_narrower_than_the_lots_support",
        "range_wider_than_the_lots_support",
        "range_misses_the_wear_rate",
        EXECUTION_FAILURE_MODE,
    ),
    "report_reconciles_with_the_receipts": (
        "receipt_stream_unreadable",
        "measurements_are_not_a_ledger",
        "paid_session_missing_from_the_report",
        "session_not_on_the_receipt_stream",
        "session_reported_twice",
        "reference_run_counted_as_a_part_session",
        "session_counts_disagree_with_the_table",
        "part_receipts_do_not_reach_the_comparison",
        EXECUTION_FAILURE_MODE,
    ),
    "next_bench_booking": (
        "plan_is_not_a_bookable_session",
        "plan_books_a_part_stores_does_not_hold",
        "plan_exceeds_bench_hours",
        "plan_books_a_rig_that_is_not_open",
        "plan_leaves_the_two_rigs_uncompared",
        "stopped_with_hours_and_parts_in_hand",
        EXECUTION_FAILURE_MODE,
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    name: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for name, modes in FAILURE_MODES.items()
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def wear_rate_ratio(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def correction_survives_the_bench_schedule(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def ratio_range_is_honest(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_reconciles_with_the_receipts(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_bench_booking(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
