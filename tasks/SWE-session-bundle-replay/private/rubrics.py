"""The five binary project rubrics for the session bundle."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "secret_redaction": (
        "candidate_execution_failed",
        "secret_left_in_the_error_text",
        "secret_left_in_the_recorded_output",
        "redaction_changed_the_record",
        "unprotected_record_was_still_redacted",
    ),
    "output_attribution": (
        "candidate_execution_failed",
        "outputs_borrowed_from_another_cell",
        "stdout_carries_the_result",
        "stderr_folded_into_stdout",
        "recorded_event_does_not_match_the_cell",
    ),
    "recorder_lifetime": (
        "candidate_execution_failed",
        "refused_start_changed_the_recording",
        "refused_start_did_not_raise",
        "recording_changed_the_cell",
        "cell_missing_from_the_bundle",
        "cell_recorded_twice",
        "extra_cell_in_the_bundle",
        "bundle_the_console_refuses",
    ),
    "bundle_admission": (
        "candidate_execution_failed",
        "edited_bundle_ran_to_the_end",
        "edited_bundle_half_ran",
        "load_admitted_a_faulty_file",
        "sound_bundle_refused",
        "rejection_did_not_name_the_faults",
    ),
    "replay_isolation": (
        "candidate_execution_failed",
        "replay_ran_past_the_failed_cell",
        "replay_stopped_at_a_cell_it_should_have_run",
        "replay_cell_count_did_not_match_file",
        "replay_report_did_not_match_execution",
        "replay_took_the_recorded_numbering",
        "quiet_replay_numbered_the_console",
        "replay_would_not_open_the_file",
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


def secret_redaction(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def output_attribution(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def recorder_lifetime(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def bundle_admission(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def replay_isolation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
