"""The five binary project rubrics for the estate policy audit."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "unit_scope_coverage": (
        "candidate_execution_failed",
        "waiver_covered_a_second_unit",
        "waiver_missed_its_unit",
        "waiver_covered_part_of_its_unit",
        "coverage_changed_with_layout",
        "report_filter_disagreed",
    ),
    "region_extent": (
        "candidate_execution_failed",
        "region_outlived_its_block",
        "region_did_not_cover_its_block",
        "nested_end_cleared_the_outer_waiver",
        "file_wide_region_stopped_early",
        "unmatched_end_started_region",
    ),
    "selector_resolution": (
        "candidate_execution_failed",
        "unknown_selector_waived_the_unit",
        "disabled_selector_waived_the_unit",
        "named_selector_waived_another_rule",
        "resolvable_selector_waived_nothing",
    ),
    "suppression_accounting": (
        "candidate_execution_failed",
        "counts_do_not_sum",
        "blanket_booked_as_specific",
        "reported_count_disagrees",
        "counter_split_disagreed",
    ),
    "audit_run_equality": (
        "candidate_execution_failed",
        "audit_hid_findings",
        "report_altered_a_finding",
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple((mode for mode in modes if mode != "candidate_execution_failed"))
    for rubric_id, modes in FAILURE_MODES.items()
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def unit_scope_coverage(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def region_extent(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def selector_resolution(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def suppression_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def audit_run_equality(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
