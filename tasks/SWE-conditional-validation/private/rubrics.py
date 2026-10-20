"""The five binary project rubrics for the order platform's write path."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "admission_matches_reference": (
        "candidate_execution_failed",
        "write_path_operation_failed",
        "payload_wrongly_refused",
        "payload_wrongly_accepted",
        "admitted_item_wrong",
    ),
    "update_guarded_by_the_store": (
        "candidate_execution_failed",
        "update_path_operation_failed",
        "violating_update_committed",
        "dependent_removal_committed",
        "caller_condition_dropped",
        "harmless_update_refused",
        "update_result_wrong",
    ),
    "stored_items_stay_reachable": (
        "candidate_execution_failed",
        "read_path_operation_failed",
        "stored_item_not_returned",
        "projected_read_failed",
        "legacy_item_update_refused",
        "legacy_item_update_wrong",
    ),
    "contract_agrees_with_the_writer": (
        "candidate_execution_failed",
        "contract_operation_failed",
        "contract_accepts_what_the_writer_refuses",
        "contract_refuses_what_the_writer_accepts",
        "rebuilt_schema_behaves_differently",
    ),
    "declarations_are_enforceable": (
        "candidate_execution_failed",
        "review_operation_failed",
        "physical_name_collision_accepted",
        "key_count_declaration_accepted",
        "unenforceable_declaration_accepted",
        "enforceable_declaration_refused",
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


def admission_matches_reference(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def update_guarded_by_the_store(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def stored_items_stay_reachable(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def contract_agrees_with_the_writer(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def declarations_are_enforceable(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
