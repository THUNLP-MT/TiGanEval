"Five binary project rubrics for the whiteboard merge."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "convergent_board_state": (
        "candidate_execution_failed",
        "sync_stopped_with_an_error",
        "laptops_show_different_cards",
        "redelivery_changed_the_card",
    ),
    "causal_edit_precedence": (
        "candidate_execution_failed",
        "sync_stopped_with_an_error",
        "replaced_value_came_back",
        "card_field_shows_no_value",
        "card_field_shows_an_unknown_value",
    ),
    "clear_scope_preserves_unseen_edits": (
        "candidate_execution_failed",
        "sync_stopped_with_an_error",
        "clear_removed_an_edit_its_author_never_saw",
        "cleared_field_still_shows_a_value",
    ),
    "state_vector_matches_what_it_holds": (
        "candidate_execution_failed",
        "sync_stopped_with_an_error",
        "laptop_claims_edits_it_does_not_have",
        "laptop_asks_for_the_whole_session_again",
    ),
    "merge_account_matches_card": (
        "candidate_execution_failed",
        "sync_stopped_with_an_error",
        "operation_missing_from_the_account",
        "account_lists_an_operation_never_handed",
        "account_places_operation_on_wrong_field",
        "waiting_operation_not_pending",
        "settled_operation_left_pending",
        "account_names_a_value_the_card_does_not_show",
        "edit_listed_twice_in_the_account",
        "account_blames_an_edit_that_did_not_replace_it",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "convergent_board_state": (
        "sync_stopped_with_an_error",
        "redelivery_changed_the_card",
        "laptops_show_different_cards",
    ),
    "causal_edit_precedence": (
        "sync_stopped_with_an_error",
        "replaced_value_came_back",
        "card_field_shows_no_value",
        "card_field_shows_an_unknown_value",
    ),
    "clear_scope_preserves_unseen_edits": (
        "sync_stopped_with_an_error",
        "clear_removed_an_edit_its_author_never_saw",
        "cleared_field_still_shows_a_value",
    ),
    "state_vector_matches_what_it_holds": (
        "sync_stopped_with_an_error",
        "laptop_claims_edits_it_does_not_have",
        "laptop_asks_for_the_whole_session_again",
    ),
    "merge_account_matches_card": (
        "sync_stopped_with_an_error",
        "operation_missing_from_the_account",
        "account_lists_an_operation_never_handed",
        "account_places_operation_on_wrong_field",
        "waiting_operation_not_pending",
        "settled_operation_left_pending",
        "account_names_a_value_the_card_does_not_show",
        "edit_listed_twice_in_the_account",
        "account_blames_an_edit_that_did_not_replace_it",
    ),
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def convergent_board_state(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def causal_edit_precedence(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def clear_scope_preserves_unseen_edits(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def state_vector_matches_what_it_holds(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def merge_account_matches_card(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
