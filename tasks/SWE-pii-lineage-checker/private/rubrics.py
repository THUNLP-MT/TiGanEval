"""The five binary project rubrics for the lineage checker."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "flow_matches_the_field_rules": (
        "candidate_execution_failed",
        "scan_step_failed",
        "leaking_export_missed",
        "clean_export_flagged",
    ),
    "verdict_survives_step_extraction": (
        "candidate_execution_failed",
        "scan_step_failed",
        "export_lost_when_the_step_moved",
        "export_appeared_when_the_step_moved",
    ),
    "report_independent_of_scan_order": (
        "candidate_execution_failed",
        "scan_step_failed",
        "finding_lost_in_one_order",
        "rows_ordered_by_scan_order",
        "report_out_of_gate_order",
    ),
    "one_row_per_leaking_export": (
        "candidate_execution_failed",
        "scan_step_failed",
        "leaking_export_unreported",
        "export_flagged_twice",
        "clean_export_reported",
        "report_row_mislabels_export",
        "report_row_is_not_an_export",
    ),
    "existing_audit_rows_unchanged": (
        "candidate_execution_failed",
        "scan_step_failed",
        "existing_row_dropped",
        "existing_row_changed",
        "unexpected_existing_row",
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


def flow_matches_the_field_rules(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def verdict_survives_step_extraction(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_independent_of_scan_order(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def one_row_per_leaking_export(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def existing_audit_rows_unchanged(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
