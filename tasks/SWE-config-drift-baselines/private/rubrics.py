"The five binary project rubrics for the estate compliance service."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "drift_record_identity": (
        "candidate_execution_failed",
        "duplicate_open_records",
        "resolved_record_reused",
        "record_identity_reset",
        "record_reopened_after_redeclaration",
        "record_reference_changed",
        "record_severity_disagrees",
        "change_not_on_the_list",
    ),
    "drift_lifecycle": (
        "candidate_execution_failed",
        "cleared_drift_not_resolved",
        "resolved_while_still_true",
        "triage_decision_dropped",
        "triage_decision_reopened",
        "resolution_restamped",
    ),
    "compliance_accounting": (
        "candidate_execution_failed",
        "nightly_number_missing",
        "missing_service_uncounted",
        "population_not_the_baseline",
        "service_counts_disagree",
        "severity_counters_disagree",
        "score_off_the_reference",
    ),
    "baseline_state_integrity": (
        "candidate_execution_failed",
        "scan_without_a_baseline_scored",
        "scan_without_a_baseline_not_refused",
        "two_active_baselines",
        "deleted_baseline_left_records",
        "delete_removed_other_records",
    ),
    "observed_config_normalisation": (
        "candidate_execution_failed",
        "unchanged_field_reported",
        "absent_field_reported",
        "stored_values_not_canonical",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple(mode for mode in modes if mode != "candidate_execution_failed")
    for rubric_id, modes in FAILURE_MODES.items()
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def drift_record_identity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def drift_lifecycle(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def compliance_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def baseline_state_integrity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def observed_config_normalisation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
