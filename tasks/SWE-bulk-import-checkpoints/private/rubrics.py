"""Five binary project rubrics for the nightly catalogue load."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "exactly_once_import_completion": (
        "candidate_execution_failed",
        "run_raised_the_feed_error",
        "run_raised_the_warehouse_error",
        "run_raised_its_own_error",
        "import_did_not_complete",
        "rows_missing_after_resume",
        "rows_duplicated_after_resume",
        "rows_incorrect_after_resume",
    ),
    "invalid_row_rejection_integrity": (
        "candidate_execution_failed",
        "invariant_violated_in_committed_state",
        "invalid_row_not_reported",
        "rejection_reason_incorrect",
        "invalid_row_reported_more_than_once",
    ),
    "resume_state_integrity": (
        "candidate_execution_failed",
        "progress_not_checkpointed",
        "foreign_source_changed_state",
        "foreign_source_returned_no_report",
        "foreign_source_not_refused",
        "committed_work_repeated",
    ),
    "bounded_transaction_work": (
        "candidate_execution_failed",
        "durable_state_changed_without_transaction",
        "source_buffered_before_first_commit",
        "transaction_batch_too_large",
        "transaction_count_exceeded",
    ),
    "clean_idempotent_completion": (
        "candidate_execution_failed",
        "next_export_did_not_complete",
        "next_export_rows_missing",
        "next_export_rows_unexpected",
        "next_export_rows_incorrect",
        "import_bookkeeping_retained",
        "completion_metadata_not_restored",
        "repeat_import_did_not_complete",
        "repeat_import_rewrote_database",
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "exactly_once_import_completion": (
        "run_raised_the_feed_error",
        "run_raised_the_warehouse_error",
        "run_raised_its_own_error",
        "import_did_not_complete",
        "rows_missing_after_resume",
        "rows_duplicated_after_resume",
        "rows_incorrect_after_resume",
    ),
    "invalid_row_rejection_integrity": (
        "invariant_violated_in_committed_state",
        "invalid_row_not_reported",
        "rejection_reason_incorrect",
        "invalid_row_reported_more_than_once",
    ),
    "resume_state_integrity": (
        "progress_not_checkpointed",
        "foreign_source_changed_state",
        "foreign_source_returned_no_report",
        "foreign_source_not_refused",
        "committed_work_repeated",
    ),
    "bounded_transaction_work": (
        "durable_state_changed_without_transaction",
        "source_buffered_before_first_commit",
        "transaction_batch_too_large",
        "transaction_count_exceeded",
    ),
    "clean_idempotent_completion": (
        "import_bookkeeping_retained",
        "completion_metadata_not_restored",
        "next_export_did_not_complete",
        "next_export_rows_missing",
        "next_export_rows_unexpected",
        "next_export_rows_incorrect",
        "repeat_import_rewrote_database",
        "repeat_import_did_not_complete",
    ),
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def exactly_once_import_completion(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def invalid_row_rejection_integrity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def resume_state_integrity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def bounded_transaction_work(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def clean_idempotent_completion(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
