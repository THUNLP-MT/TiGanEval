"""The five binary project judgements for the tile-rendering package."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "every_cell_is_produced": (
        "candidate_execution_failed",
        "pass_ended_with_an_error",
        "cells_left_unproduced",
        "cell_produced_more_than_once",
        "frame_cell_overwritten",
        "constant_axis_band_overwritten",
    ),
    "boundary_reads_match_the_contract": (
        "candidate_execution_failed",
        "pass_ended_with_an_error",
        "edge_cell_disagrees_with_the_contract",
        "out_of_reach_read_not_filled",
    ),
    "axes_are_mapped_independently": (
        "candidate_execution_failed",
        "pass_ended_with_an_error",
        "axis_modes_swapped",
        "mode_spelling_changes_the_tile",
        "corner_cell_disagrees_with_the_contract",
    ),
    "refuses_rather_than_substitutes": (
        "candidate_execution_failed",
        "unusable_mode_setting_produced_a_tile",
        "out_of_reach_coefficient_read_produced_a_tile",
        "frame_buffer_cell_type_produced_a_tile",
        "frame_buffer_shape_produced_a_tile",
        "refused_job_left_the_buffer_changed",
        "refused_job_wrote_before_stopping",
    ),
    "recorded_passes_keep_their_output": (
        "candidate_execution_failed",
        "pass_ended_with_an_error",
        "declared_dtype_not_kept",
        "kept_margin_overwritten",
        "frame_buffer_not_updated",
        "default_tile_changed",
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


def every_cell_is_produced(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def boundary_reads_match_the_contract(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def axes_are_mapped_independently(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def refuses_rather_than_substitutes(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def recorded_passes_keep_their_output(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
