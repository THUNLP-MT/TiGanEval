"The five binary project rubrics for the scene checkpoint feature."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "isolated_checkpoint_value": (
        "candidate_execution_failed",
        "editor_step_failed",
        "checkpoint_moved_with_the_level",
        "revert_left_the_level_wired_to_the_checkpoint",
        "second_revert_gave_a_different_level",
        "revert_did_not_reproduce_the_checkpoint",
    ),
    "exact_prop_restore": (
        "candidate_execution_failed",
        "revert_left_a_surplus_trait",
        "revert_dropped_a_recorded_trait",
        "revert_turned_a_tag_into_data",
        "revert_kept_the_new_value",
    ),
    "preserved_prop_identity": (
        "candidate_execution_failed",
        "destroyed_prop_not_brought_back",
        "prop_came_back_under_a_new_id",
        "surplus_prop_survived_the_revert",
        "link_points_somewhere_else",
        "recorded_link_missing",
        "link_recorded_twice",
        "session_entity_disturbed",
    ),
    "refused_revert_leaves_level": (
        "candidate_execution_failed",
        "broken_checkpoint_left_the_level_half_changed",
        "broken_checkpoint_applied",
        "refusal_used_the_wrong_error",
        "good_checkpoint_refused",
        "broken_prop_file_left_the_prop_half_changed",
        "broken_prop_file_applied",
        "prop_refusal_used_the_wrong_error",
        "good_prop_file_refused",
    ),
    "canonical_change_report": (
        "candidate_execution_failed",
        "panel_report_wrong_shape",
        "panel_flagged_an_unchanged_prop",
        "panel_missed_a_change",
        "panel_reported_a_change_that_is_not_there",
        "panel_rows_out_of_order",
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


def isolated_checkpoint_value(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def exact_prop_restore(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def preserved_prop_identity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def refused_revert_leaves_level(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def canonical_change_report(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
