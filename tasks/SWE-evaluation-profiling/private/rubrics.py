"""The five binary project rubrics for the decision service."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "profiling_is_not_causal": (
        "candidate_execution_failed",
        "engine_operation_failed",
        "decision_changed_by_profiling",
        "decision_disagrees_with_policy",
        "work_changed_by_profiling",
    ),
    "definition_level_attribution": (
        "candidate_execution_failed",
        "profile_row_keys_not_definitions",
        "entered_definition_missing",
        "unentered_definition_reported",
        "definition_success_count_wrong",
    ),
    "reuse_is_not_evaluation": (
        "candidate_execution_failed",
        "evaluation_count_wrong",
        "reuse_never_recorded",
        "reuse_count_wrong",
    ),
    "profile_scoped_to_one_decision": (
        "candidate_execution_failed",
        "profile_missing_when_enabled",
        "profile_attached_when_disabled",
        "profile_depends_on_earlier_requests",
        "retired_bundle_rules_reported",
        "earlier_profile_changed_by_later_decision",
    ),
    "rollup_preserves_the_run": (
        "candidate_execution_failed",
        "rollup_operation_failed",
        "package_key_not_package",
        "package_totals_disagree_with_run",
        "merged_shard_counts_wrong",
        "derived_profile_aliases_source",
        "success_rate_wrong",
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


def profiling_is_not_causal(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def definition_level_attribution(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def reuse_is_not_evaluation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def profile_scoped_to_one_decision(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def rollup_preserves_the_run(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
