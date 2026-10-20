"Five binary project rubrics for the order-fulfilment workflow engine."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "scope_ownership": (
        "candidate_execution_failed",
        "value_read_back_wrong",
        "state_lost_its_data",
        "left_state_still_carried",
    ),
    "entry_isolation": (
        "candidate_execution_failed",
        "entry_started_from_the_last_pass",
        "orders_reading_each_others_data",
        "the_chart_itself_was_changed",
    ),
    "resume_depth": (
        "candidate_execution_failed",
        "resume_came_back_empty",
        "resume_restored_too_deep",
        "resume_came_back_changed",
    ),
    "change_audit": (
        "candidate_execution_failed",
        "audit_line_missing",
        "audit_line_repeated",
        "audit_line_wrong_values",
        "audit_carried_the_previous_step",
    ),
    "refused_writes": (
        "candidate_execution_failed",
        "bad_write_went_through",
        "step_broke_instead_of_refusing",
        "refused_with_the_wrong_code",
        "good_write_refused",
        "refusal_changed_the_data",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "scope_ownership": (
        "value_read_back_wrong",
        "state_lost_its_data",
        "left_state_still_carried",
    ),
    "entry_isolation": (
        "the_chart_itself_was_changed",
        "entry_started_from_the_last_pass",
        "orders_reading_each_others_data",
    ),
    "resume_depth": (
        "resume_came_back_empty",
        "resume_restored_too_deep",
        "resume_came_back_changed",
    ),
    "change_audit": (
        "audit_line_missing",
        "audit_carried_the_previous_step",
        "audit_line_wrong_values",
        "audit_line_repeated",
    ),
    "refused_writes": (
        "bad_write_went_through",
        "step_broke_instead_of_refusing",
        "refusal_changed_the_data",
        "refused_with_the_wrong_code",
        "good_write_refused",
    ),
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def scope_ownership(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def entry_isolation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def resume_depth(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def change_audit(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def refused_writes(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
