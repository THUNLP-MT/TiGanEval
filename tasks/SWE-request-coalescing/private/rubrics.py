"Five binary project rubrics for the summary relay."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "delivered_response_equivalence": (
        "candidate_execution_failed",
        "response_from_another_scope",
        "refusal_not_delivered_to_unauthorized_caller",
        "summary_after_the_rendering_failed",
        "response_missing_leading_chunks",
        "response_pieces_out_of_order",
        "refusal_instead_of_the_summary",
        "response_did_not_match_reference",
    ),
    "every_call_answered_once": (
        "candidate_execution_failed",
        "waiters_unresolved_after_the_backend_failed",
        "waiters_unresolved_after_the_first_caller_left",
        "desk_the_directory_dropped_left_unanswered",
        "call_left_unanswered",
        "call_answered_twice",
    ),
    "upstream_execution_conservation": (
        "candidate_execution_failed",
        "duplicate_upstream_executions",
        "upstream_execution_without_a_caller",
        "upstream_execution_for_the_wrong_request",
        "no_execution_after_the_backend_failed",
        "episode_ran_no_upstream_execution",
    ),
    "usage_ledger_completeness": (
        "candidate_execution_failed",
        "usage_entry_has_wrong_shape",
        "usage_entry_missing_for_an_answered_caller",
        "duplicate_usage_entries_for_an_answered_caller",
        "usage_entry_attributed_to_another_caller",
        "usage_entry_does_not_match_the_call",
        "usage_entry_for_a_caller_that_was_never_answered",
        "usage_entry_does_not_record_the_outcome",
        "sharing_statistics_do_not_match",
    ),
    "outcome_independent_of_arrival_order": (
        "candidate_execution_failed",
        "outcome_changed_with_the_arrival_order",
        "outcome_changed_with_the_piece_boundaries",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "delivered_response_equivalence": (
        "response_from_another_scope",
        "refusal_not_delivered_to_unauthorized_caller",
        "summary_after_the_rendering_failed",
        "response_missing_leading_chunks",
        "response_pieces_out_of_order",
        "refusal_instead_of_the_summary",
        "response_did_not_match_reference",
    ),
    "every_call_answered_once": (
        "waiters_unresolved_after_the_backend_failed",
        "waiters_unresolved_after_the_first_caller_left",
        "desk_the_directory_dropped_left_unanswered",
        "call_answered_twice",
        "call_left_unanswered",
    ),
    "upstream_execution_conservation": (
        "duplicate_upstream_executions",
        "upstream_execution_without_a_caller",
        "upstream_execution_for_the_wrong_request",
        "no_execution_after_the_backend_failed",
        "episode_ran_no_upstream_execution",
    ),
    "usage_ledger_completeness": (
        "usage_entry_has_wrong_shape",
        "usage_entry_missing_for_an_answered_caller",
        "usage_entry_attributed_to_another_caller",
        "usage_entry_does_not_match_the_call",
        "usage_entry_for_a_caller_that_was_never_answered",
        "duplicate_usage_entries_for_an_answered_caller",
        "usage_entry_does_not_record_the_outcome",
        "sharing_statistics_do_not_match",
    ),
    "outcome_independent_of_arrival_order": (
        "outcome_changed_with_the_arrival_order",
        "outcome_changed_with_the_piece_boundaries",
    ),
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def delivered_response_equivalence(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def every_call_answered_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def upstream_execution_conservation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def usage_ledger_completeness(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def outcome_independent_of_arrival_order(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
