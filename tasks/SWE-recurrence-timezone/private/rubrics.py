"The five binary project reviews for the reminder schedule engine."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "local_time_preserved": (
        "candidate_execution_failed",
        "schedule_call_failed",
        "series_length_wrong",
        "occurrence_drifted_from_local_time",
        "standing_series_unanswered",
        "late_stretch_unanswered",
    ),
    "transition_occurrence_policy": (
        "candidate_execution_failed",
        "schedule_call_failed",
        "gap_occurrence_missing",
        "gap_occurrence_moved",
        "ambiguous_occurrence_missing",
        "ambiguous_occurrence_moved",
        "gap_occurrence_duplicated",
        "ambiguous_occurrence_duplicated",
        "transition_series_length_wrong",
        "transition_series_occurrence_moved",
    ),
    "exported_rule_round_trip": (
        "candidate_execution_failed",
        "schedule_call_failed",
        "export_unreadable",
        "zone_lost_in_export",
        "start_moved_in_export",
        "series_name_changed_in_export",
        "series_repeat_changed_in_export",
        "series_bound_kind_changed_in_export",
        "series_count_changed_in_export",
        "series_end_moved",
        "export_not_stable",
    ),
    "merged_feed_deduplication": (
        "candidate_execution_failed",
        "schedule_call_failed",
        "duplicate_reminder_in_merge",
        "merged_reminder_missing",
        "merged_reminder_unexpected",
        "merge_not_ascending",
    ),
    "window_slice_partition": (
        "candidate_execution_failed",
        "schedule_call_failed",
        "occurrence_outside_window",
        "slice_duplicated_occurrence",
        "slice_dropped_occurrence",
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


def local_time_preserved(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def transition_occurrence_policy(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def exported_rule_round_trip(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def merged_feed_deduplication(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def window_slice_partition(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
