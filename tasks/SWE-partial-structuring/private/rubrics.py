"Five binary project rubrics for the nightly provider ingest."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "field_provenance_accounting": (
        "candidate_execution_failed",
        "field_accounting_not_reported",
        "absent_column_reported_as_provider_data",
        "fallback_value_reported_as_provider_data",
        "derived_column_in_the_accounting",
        "supplied_column_on_both_lists",
        "name_that_is_not_a_column_of_the_file",
        "supplied_column_on_neither_list",
        "clean_column_reported_as_a_gap",
        "read_whole_although_the_ticket_has_columns_on_it",
        "not_read_whole_although_the_ticket_is_empty",
    ),
    "publishable_or_withheld": (
        "candidate_execution_failed",
        "record_published_without_a_required_column",
        "record_withheld_although_every_gap_has_a_fallback",
        "record_withheld_although_nothing_is_missing",
        "published_column_holds_neither_the_file_nor_the_fallback",
        "computed_column_does_not_match_the_record",
        "publisher_failed_during_the_drop",
    ),
    "diagnosis_matches_the_strict_reading": (
        "candidate_execution_failed",
        "diagnosis_not_reported",
        "absent_column_produces_no_line",
        "line_missing_from_the_diagnosis",
        "line_the_strict_reading_does_not_give",
        "the_same_line_twice_on_the_ticket",
    ),
    "nested_and_collection_recovery": (
        "candidate_execution_failed",
        "recovered_block_reported_as_provider_data",
        "nested_block_discarded_although_part_of_it_read",
        "published_block_is_not_the_block_the_file_gave_us",
        "published_list_does_not_match_the_file",
    ),
    "corrections_fold_into_the_reading": (
        "candidate_execution_failed",
        "corrections_not_folded_into_the_reading",
        "correction_lost_a_column_that_had_already_read",
        "correction_overwrote_a_column_that_had_already_read",
        "correction_left_the_record_unpublishable",
        "corrected_reading_still_shows_the_column_as_a_gap",
        "corrected_record_does_not_hold_what_support_sent",
        "correction_outcome_depends_on_how_it_arrives",
        "the_earlier_reading_changed_when_the_correction_arrived",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "field_provenance_accounting": (
        "field_accounting_not_reported",
        "absent_column_reported_as_provider_data",
        "fallback_value_reported_as_provider_data",
        "derived_column_in_the_accounting",
        "supplied_column_on_both_lists",
        "name_that_is_not_a_column_of_the_file",
        "supplied_column_on_neither_list",
        "clean_column_reported_as_a_gap",
        "read_whole_although_the_ticket_has_columns_on_it",
        "not_read_whole_although_the_ticket_is_empty",
    ),
    "publishable_or_withheld": (
        "record_published_without_a_required_column",
        "record_withheld_although_every_gap_has_a_fallback",
        "record_withheld_although_nothing_is_missing",
        "published_column_holds_neither_the_file_nor_the_fallback",
        "computed_column_does_not_match_the_record",
        "publisher_failed_during_the_drop",
    ),
    "diagnosis_matches_the_strict_reading": (
        "diagnosis_not_reported",
        "absent_column_produces_no_line",
        "line_missing_from_the_diagnosis",
        "line_the_strict_reading_does_not_give",
        "the_same_line_twice_on_the_ticket",
    ),
    "nested_and_collection_recovery": (
        "recovered_block_reported_as_provider_data",
        "nested_block_discarded_although_part_of_it_read",
        "published_block_is_not_the_block_the_file_gave_us",
        "published_list_does_not_match_the_file",
    ),
    "corrections_fold_into_the_reading": (
        "corrections_not_folded_into_the_reading",
        "correction_lost_a_column_that_had_already_read",
        "correction_overwrote_a_column_that_had_already_read",
        "correction_left_the_record_unpublishable",
        "corrected_reading_still_shows_the_column_as_a_gap",
        "corrected_record_does_not_hold_what_support_sent",
        "correction_outcome_depends_on_how_it_arrives",
        "the_earlier_reading_changed_when_the_correction_arrived",
    ),
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def field_provenance_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def publishable_or_withheld(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def diagnosis_matches_the_strict_reading(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def nested_and_collection_recovery(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def corrections_fold_into_the_reading(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
