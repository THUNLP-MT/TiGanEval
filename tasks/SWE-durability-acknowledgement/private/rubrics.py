"The five binary project checks for the storage engine's write path."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "durable_watermark_matches_log": (
        "candidate_execution_failed",
        "session_output_incomplete",
        "tracker_call_failed",
        "watermark_ahead_of_the_log",
        "watermark_went_backwards",
        "watermark_behind_the_log",
    ),
    "release_never_precedes_the_log": (
        "candidate_execution_failed",
        "session_output_incomplete",
        "tracker_call_failed",
        "event_released_an_unlogged_write",
        "waiter_released_an_unlogged_write",
    ),
    "one_event_per_sync_commit": (
        "candidate_execution_failed",
        "session_output_incomplete",
        "tracker_call_failed",
        "durability_event_claimed_a_lost_write",
        "durability_event_carried_a_false_error",
        "durability_event_carried_wrong_error",
        "durability_event_missing_for_a_stranded_write",
        "durability_event_missing_for_a_landed_write",
        "durability_event_duplicated",
        "durability_event_without_a_sync",
        "durability_event_fields_wrong",
        "durability_event_at_wrong_step",
        "durability_event_without_sync_completion",
    ),
    "waiters_settle_exactly_once": (
        "candidate_execution_failed",
        "session_output_incomplete",
        "tracker_call_failed",
        "waiter_left_unresolved_at_close",
        "waiter_left_parked_on_a_landed_write",
        "waiter_resolved_more_than_once",
        "waiter_blocked_after_the_log_broke",
        "error_not_latched",
        "pending_waiter_count_wrong",
        "waiter_failed_a_landed_write",
        "waiter_resolved_without_required_error",
        "waiter_error_did_not_match_first_failure",
    ),
    "accounting_independent_of_pipeline_shape": (
        "candidate_execution_failed",
        "session_output_incomplete",
        "tracker_call_failed",
        "wait_stalled_without_a_listener",
        "state_differed_without_a_listener",
        "event_count_lost_without_a_listener",
        "grouping_changed_what_became_durable",
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


def durable_watermark_matches_log(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def release_never_precedes_the_log(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def one_event_per_sync_commit(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def waiters_settle_exactly_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def accounting_independent_of_pipeline_shape(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
