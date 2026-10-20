"The five binary project checks for the quote route's failure review."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import EXECUTION_FAILURE_MODE, RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "window_failure_rate": (
        "report_field_missing_or_unreadable",
        "attempts_counted_as_operations",
        "edge_probes_retained",
        "correction_keyed_on_date",
        "window_failure_rate_disagrees",
        EXECUTION_FAILURE_MODE,
    ),
    "reported_range": (
        "range_absent_or_zero_width",
        "range_excludes_supported_value",
        "range_narrower_than_unresolved_minutes",
        "range_wider_than_the_counters_support",
        EXECUTION_FAILURE_MODE,
    ),
    "next_trace_plan": (
        "plan_did_not_name_a_minute_or_a_stop",
        "outside_retention",
        "repeats_a_paid_minute",
        "less_informative_than_named_minutes",
        "exceeds_units",
        "stopped_with_minutes_unresolved",
        EXECUTION_FAILURE_MODE,
    ),
    "receipt_accounting": (
        "receipt_ledger_unreadable",
        "trace_units_are_not_a_ledger",
        "receipts_unaccounted",
        "resolved_minute_without_receipt",
        "trace_line_disagrees_with_receipt",
        "unit_reported_twice",
        EXECUTION_FAILURE_MODE,
    ),
    "correction_invariant": (
        "report_field_missing_or_unreadable",
        "moves_with_rollout_day",
        "moves_with_retry_cap",
        "moves_with_spill_fraction",
        "later_report_fields_disagree",
        "moves_with_unfinished_rollout",
        EXECUTION_FAILURE_MODE,
    ),
}

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    name: tuple(mode for mode in modes if mode != EXECUTION_FAILURE_MODE)
    for name, modes in FAILURE_MODES.items()
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def window_failure_rate(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def reported_range(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_trace_plan(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def receipt_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def correction_invariant(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
