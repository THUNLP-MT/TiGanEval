"The five binary project rubrics for the plugin sandbox's dump tool."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "consistent_cut": (
        "candidate_execution_failed",
        "full_capture_not_taken",
        "capture_target_set_mismatch",
        "capture_named_wrong_epoch",
        "captured_books_do_not_balance",
        "capture_read_across_epochs",
    ),
    "capture_holds_still": (
        "candidate_execution_failed",
        "capture_followed_the_host",
        "capture_handed_out_the_stored_buffer",
    ),
    "incremental_chain": (
        "candidate_execution_failed",
        "incremental_not_taken",
        "incremental_target_set_mismatch",
        "incremental_named_wrong_epoch",
        "chain_reconstruction_mismatch",
        "delta_not_against_reconstructed_baseline",
        "incremental_stored_the_whole_arena",
    ),
    "restore_all_or_nothing": (
        "candidate_execution_failed",
        "refused_restore_wrote_anyway",
        "detached_target_accepted",
        "foreign_target_accepted",
        "mismatched_target_accepted",
        "sound_restore_refused",
        "restore_reported_wrong_reason",
        "restore_touched_the_wrong_plugins",
    ),
    "restored_arena_exact": (
        "candidate_execution_failed",
        "post_capture_bytes_survived",
        "restored_arena_differs",
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


def consistent_cut(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def capture_holds_still(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def incremental_chain(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def restore_all_or_nothing(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def restored_arena_exact(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
