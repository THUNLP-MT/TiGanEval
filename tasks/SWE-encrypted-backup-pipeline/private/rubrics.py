"The five binary project rubrics for the nightly archive."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "published_object_restores": (
        "candidate_execution_failed",
        "restore_path_would_not_open_it",
        "the_recovered_stream_is_not_compressed",
        "restored_bytes_are_not_the_dump",
    ),
    "destination_inventory_conserved": (
        "candidate_execution_failed",
        "object_left_after_a_key_failure",
        "destination_opened_without_one_usable_key",
        "object_left_after_a_write_failed",
        "object_finalized_before_all_destinations_read_back",
        "night_missing_from_a_destination",
        "object_left_open",
    ),
    "report_equals_restorable_state": (
        "candidate_execution_failed",
        "no_report_for_the_night",
        "reported_complete_without_a_published_object",
        "reported_complete_but_not_restorable",
        "usable_night_reported_as_lost",
    ),
    "key_provenance_recorded": (
        "candidate_execution_failed",
        "object_does_not_name_the_key_that_sealed_it",
        "ambiguous_key_configuration_was_resolved",
        "object_sealed_with_a_retired_key",
    ),
    "window_drill_opens_any_night": (
        "candidate_execution_failed",
        "plain_night_would_not_open",
        "sealed_night_would_not_open",
        "renamed_object_opened_as_the_wrong_kind",
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


def published_object_restores(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def destination_inventory_conserved(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_equals_restorable_state(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def key_provenance_recorded(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def window_drill_opens_any_night(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
