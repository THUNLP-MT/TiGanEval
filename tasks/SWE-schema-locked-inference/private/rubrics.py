"""Five binary project rubrics for the schema-locked inference project."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "persisted_schema_completeness": (
        "candidate_execution_failed",
        "baseline_fit_failed",
        "schema_artifact_missing",
        "description_artifact_missing",
        "model_artifact_missing",
        "schema_artifact_incomplete",
        "schema_encoding_disagrees_with_scoring",
        "description_disagrees_with_schema",
        "schema_does_not_describe_model_input",
        "model_artifact_not_fitted",
        "export_failed_at_baseline",
        "export_disagrees_with_schema",
        "export_lists_different_features",
        "schema_drop_record_wrong",
    ),
    "consistent_inference_across_consumers": (
        "candidate_execution_failed",
        "consumer_call_failed",
        "consumer_inputs_disagree",
        "consumer_predictions_disagree",
        "consumer_prediction_not_from_model",
        "request_form_changes_input",
        "training_scoring_inputs_disagree",
        "export_disagrees_with_consumers",
    ),
    "schema_violation_refusal": (
        "candidate_execution_failed",
        "missing_source_not_refused",
        "conflicting_sources_not_refused",
        "refusal_missing_column_names",
        "model_ran_on_refused_input",
        "known_input_wrongly_refused",
        "invalid_specification_accepted",
        "model_ran_on_invalid_specification",
    ),
    "caller_contract_error_reporting": (
        "candidate_execution_failed",
        "serve_raised_instead_of_reporting",
        "serve_failed_valid_request",
        "serve_scored_a_refusable_record",
        "serve_status_wrong",
        "serve_detail_missing_columns",
        "evaluate_did_not_refuse",
        "refusal_wrong_exception_type",
        "serve_rejected_valid_request",
    ),
    "stable_artifact_reuse": (
        "candidate_execution_failed",
        "artifacts_not_reproducible",
        "schema_depends_on_row_order",
        "model_depends_on_row_order",
        "unsupported_artifact_version_accepted",
        "unversioned_artifacts_accepted",
        "artifact_refusal_wrong_exception_type",
        "serve_artifact_refusal_wrong",
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "persisted_schema_completeness": (
        "baseline_fit_failed",
        "schema_artifact_missing",
        "model_artifact_missing",
        "description_artifact_missing",
        "schema_artifact_incomplete",
        "schema_encoding_disagrees_with_scoring",
        "description_disagrees_with_schema",
        "schema_does_not_describe_model_input",
        "model_artifact_not_fitted",
        "export_failed_at_baseline",
        "schema_drop_record_wrong",
        "export_disagrees_with_schema",
        "export_lists_different_features",
    ),
    "consistent_inference_across_consumers": (
        "consumer_call_failed",
        "consumer_inputs_disagree",
        "consumer_predictions_disagree",
        "consumer_prediction_not_from_model",
        "request_form_changes_input",
        "training_scoring_inputs_disagree",
        "export_disagrees_with_consumers",
    ),
    "schema_violation_refusal": (
        "missing_source_not_refused",
        "conflicting_sources_not_refused",
        "known_input_wrongly_refused",
        "invalid_specification_accepted",
        "model_ran_on_invalid_specification",
        "model_ran_on_refused_input",
        "refusal_missing_column_names",
    ),
    "caller_contract_error_reporting": (
        "serve_raised_instead_of_reporting",
        "serve_failed_valid_request",
        "serve_scored_a_refusable_record",
        "serve_status_wrong",
        "serve_rejected_valid_request",
        "evaluate_did_not_refuse",
        "refusal_wrong_exception_type",
        "serve_detail_missing_columns",
    ),
    "stable_artifact_reuse": (
        "unsupported_artifact_version_accepted",
        "unversioned_artifacts_accepted",
        "artifact_refusal_wrong_exception_type",
        "serve_artifact_refusal_wrong",
        "artifacts_not_reproducible",
        "schema_depends_on_row_order",
        "model_depends_on_row_order",
    ),
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def persisted_schema_completeness(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def consistent_inference_across_consumers(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def schema_violation_refusal(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def caller_contract_error_reporting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def stable_artifact_reuse(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
