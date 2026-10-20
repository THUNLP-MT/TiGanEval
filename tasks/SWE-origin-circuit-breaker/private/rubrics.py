"The five binary project rubrics for the edge gateway's call path."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "shared_origin_isolation": (
        "candidate_execution_failed",
        "healthy_origin_refused",
        "failed_origin_still_called",
        "origin_state_split_across_callers",
        "scheme_origin_collapsed",
    ),
    "half_open_admission": (
        "candidate_execution_failed",
        "probe_flood",
        "retry_took_a_second_slot",
        "retry_released_slot_early",
        "probe_slot_leaked",
        "available_probe_slot_refused",
        "rejected_probe_slot_leaked",
    ),
    "blocked_call_inertness": (
        "candidate_execution_failed",
        "blocked_call_reached_the_transport",
        "blocked_call_refreshed_the_block",
        "unguarded_call_blocked",
        "unguarded_call_counted",
    ),
    "logical_call_accounting": (
        "candidate_execution_failed",
        "retries_counted_as_failures",
        "logical_failures_not_counted",
        "probe_left_before_cooldown",
    ),
    "outcome_classification": (
        "candidate_execution_failed",
        "rejection_treated_as_success",
        "suppressed_error_not_counted",
        "rejection_counted_as_failure",
        "rejected_probe_closed_the_circuit",
        "transport_error_not_counted",
        "transform_error_not_counted",
        "successful_probe_left_half_open",
        "successful_call_did_not_reset_streak",
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


def shared_origin_isolation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def half_open_admission(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def blocked_call_inertness(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def logical_call_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def outcome_classification(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
