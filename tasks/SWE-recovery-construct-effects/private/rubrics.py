"The five binary project rubrics for the rating run's recovery region."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "single_branch_effects": (
        "candidate_execution_failed",
        "duplicate_charges_for_one_order",
        "priced_order_left_no_ledger_rows",
        "effects_kept_for_an_unpriced_order",
        "order_priced_at_wrong_value",
        "ledger_rows_do_not_match_winning_branch",
    ),
    "signal_transparency": (
        "candidate_execution_failed",
        "budget_abort_absorbed",
        "budget_abort_filed_as_a_rule_fault",
        "halt_ignored",
    ),
    "lease_conservation": (
        "candidate_execution_failed",
        "leases_open_at_the_end",
        "two_reservations_held_at_once",
        "cleanup_failure_swallowed",
        "close_never_ran_for_that_order",
        "close_count_wrong_for_order",
    ),
    "attempt_budget": (
        "candidate_execution_failed",
        "attempts_over_budget",
        "retries_spent_without_falling_back",
        "retried_order_left_unpriced",
        "retried_order_priced_by_its_branch",
        "exhaustion_answered_with_a_price",
        "exhaustion_reported_as_inner_fault",
    ),
    "label_invariance": (
        "candidate_execution_failed",
        "label_follows_message_text",
        "clause_missed_sibling_fault",
        "guard_did_not_take_its_own_label",
        "guard_took_an_unnamed_label",
        "fault_filed_under_wrong_label",
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


def single_branch_effects(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def signal_transparency(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def lease_conservation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def attempt_budget(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def label_invariance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
