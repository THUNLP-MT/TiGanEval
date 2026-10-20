"The five binary project rubrics for the fleet's kit loader."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "single_activation_per_file": (
        "candidate_execution_failed",
        "cached_kit_activated_again",
        "file_activated_under_a_second_name",
        "file_activated_again_for_another_job",
    ),
    "resolution_agreement": (
        "candidate_execution_failed",
        "shared_copy_beat_the_local_one",
        "shared_kit_read_the_pinned_list",
        "job_missed_its_own_pinned_list",
        "worker_settings_changed_the_result",
        "kit_name_not_found",
    ),
    "load_state_conservation": (
        "candidate_execution_failed",
        "cycle_not_refused",
        "failed_kit_left_behind",
        "cycle_chain_incomplete",
    ),
    "run_outcome_independence": (
        "candidate_execution_failed",
        "run_depended_on_the_queue_order",
        "half_built_kit_was_handed_out",
        "catalog_did_not_match_the_kit_files",
        "held_kits_listed_in_dispatch_order",
    ),
    "loader_diagnostics_routing": (
        "candidate_execution_failed",
        "diagnostics_went_to_the_process_stream",
        "nothing_reached_the_job_logs",
        "command_line_switch_ignored",
        "job_log_did_not_match_the_job",
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


def single_activation_per_file(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def resolution_agreement(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def load_state_conservation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def run_outcome_independence(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def loader_diagnostics_routing(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
