"""The five binary project rubrics for the handset's restore path."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "restored_screen_fidelity": (
        "candidate_execution_failed",
        "the_app_fell_over_on_a_screen",
        "restored_error_dropped",
        "restored_status_contradicts_the_screen",
        "restored_banner_is_missing",
        "restored_pages_dropped",
        "restored_screen_is_a_fresh_load",
        "restored_screen_is_not_the_copy_the_crew_left",
        "saved_screen_did_not_survive_restart",
    ),
    "restore_load_accounting": (
        "candidate_execution_failed",
        "the_app_fell_over_on_a_screen",
        "restore_counted_as_a_load",
        "completed_load_went_missing",
    ),
    "restored_query_quiescence": (
        "candidate_execution_failed",
        "the_app_fell_over_on_a_screen",
        "restored_screen_shows_a_load_that_is_not_running",
        "rebuild_left_a_finished_load_running",
        "restored_screen_varies_with_what_the_writer_caught",
    ),
    "restore_path_agreement": (
        "candidate_execution_failed",
        "the_app_fell_over_on_a_screen",
        "rebuild_dropped_the_error",
        "the_two_ways_in_disagree",
    ),
    "rebuild_freshness_merge": (
        "candidate_execution_failed",
        "the_app_fell_over_on_a_screen",
        "rebuild_overwrote_newer_rows",
        "rebuild_skipped_the_saved_error",
        "rebuild_merged_without_the_banner",
        "rebuild_left_the_screen_between_the_two",
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


def restored_screen_fidelity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def restore_load_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def restored_query_quiescence(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def restore_path_agreement(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def rebuild_freshness_merge(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
