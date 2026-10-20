"""The five binary project rubrics for the CI shard planner."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "whole_suite_assigned_once": (
        "candidate_execution_failed",
        "planner_call_failed",
        "shard_assignment_missing",
        "file_assigned_to_no_shard",
        "file_assigned_to_two_shards",
        "file_listed_twice_in_one_shard",
        "unknown_file_assigned",
    ),
    "run_pinned_plan_agreement": (
        "candidate_execution_failed",
        "retry_plan_differs",
        "plan_moved_after_recording",
        "plan_generation_not_pinned",
    ),
    "unmeasured_files_keep_the_usual_split": (
        "candidate_execution_failed",
        "cold_start_planner_failed",
        "cold_start_split_differs",
        "unmeasured_file_moved_off_its_usual_shard",
    ),
    "duration_history_conservation": (
        "candidate_execution_failed",
        "recorder_call_failed",
        "history_file_unreadable",
        "earlier_observation_lost",
        "completed_file_not_recorded",
        "file_recorded_more_than_once",
        "unrun_file_recorded",
        "unexpected_observation_recorded",
        "recorded_duration_wrong",
        "recorded_time_not_from_the_run_clock",
        "history_generation_did_not_advance",
        "history_generation_disagrees_with_entries",
    ),
    "plan_balance_honesty": (
        "candidate_execution_failed",
        "balance_report_missing",
        "plan_context_mismatch",
        "predicted_total_disagrees",
        "estimate_not_from_history",
        "slower_than_the_split_it_replaced",
        "shard_over_balance_bound",
        "plan_predicts_a_lopsided_split",
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


def whole_suite_assigned_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def run_pinned_plan_agreement(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def unmeasured_files_keep_the_usual_split(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def duration_history_conservation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def plan_balance_honesty(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
