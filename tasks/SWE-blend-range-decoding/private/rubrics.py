"The five binary project judgements for the catalogue compositor."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "untouched_shots_come_back_unchanged": (
        "candidate_execution_failed",
        "untouched_render_failed",
        "absent_block_rejected",
        "default_cut_changed_the_plate",
        "default_block_ignored_opacity",
    ),
    "source_files_survive_the_export": (
        "candidate_execution_failed",
        "resave_step_failed",
        "absent_block_replaced",
        "stored_block_length_changed",
        "split_handle_collapsed",
        "stored_word_changed",
    ),
    "backdrop_cuts_read_the_plate_beneath": (
        "candidate_execution_failed",
        "operand_render_failed",
        "backdrop_cuts_ignored",
        "under_light_not_applied",
        "backdrop_cuts_read_the_layer",
        "backdrop_is_not_the_plate_beneath",
        "layer_cuts_read_the_backdrop",
        "range_work_skipped_below_top_layer",
        "operand_weight_wrong",
    ),
    "split_grips_fade": (
        "candidate_execution_failed",
        "fade_render_failed",
        "split_grips_stepped",
        "fade_shape_wrong",
    ),
    "entries_address_declared_channels": (
        "candidate_execution_failed",
        "channel_render_failed",
        "composite_entry_applied_to_a_colour_channel",
        "transparency_entry_applied",
        "unaddressed_entry_applied",
        "colour_entries_not_applied",
        "composite_entry_not_applied",
        "channel_weight_wrong",
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


def untouched_shots_come_back_unchanged(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def source_files_survive_the_export(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def backdrop_cuts_read_the_plate_beneath(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def split_grips_fade(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def entries_address_declared_channels(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
