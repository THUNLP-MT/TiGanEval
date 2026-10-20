"Five binary project rubrics for the migration-formatter project."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "schema_semantics_preserved": (
        "candidate_execution_failed",
        "schema_changed",
        "statement_lost",
        "statement_no_longer_a_table",
        "formatted_output_unparsable",
    ),
    "formatting_is_idempotent": (
        "candidate_execution_failed",
        "second_pass_differs",
        "output_not_deterministic",
        "output_depends_on_input_formatting",
    ),
    "comments_preserved": (
        "candidate_execution_failed",
        "header_comment_swallows_statement",
        "line_comment_swallows_code",
        "block_comment_split_across_lines",
        "comment_lost_or_reordered",
    ),
    "line_width_contract": (
        "candidate_execution_failed",
        "line_over_width_with_break_available",
        "body_indent_wrong",
    ),
    "explicit_unsupported_handling": (
        "candidate_execution_failed",
        "statement_rows_incomplete",
        "unsupported_statement_modified",
        "unsupported_statement_reported_formatted",
        "supported_statement_reported_unsupported",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "schema_semantics_preserved": (
        "formatted_output_unparsable",
        "statement_lost",
        "statement_no_longer_a_table",
        "schema_changed",
    ),
    "formatting_is_idempotent": (
        "second_pass_differs",
        "output_not_deterministic",
        "output_depends_on_input_formatting",
    ),
    "comments_preserved": (
        "header_comment_swallows_statement",
        "line_comment_swallows_code",
        "block_comment_split_across_lines",
        "comment_lost_or_reordered",
    ),
    "line_width_contract": (
        "line_over_width_with_break_available",
        "body_indent_wrong",
    ),
    "explicit_unsupported_handling": (
        "statement_rows_incomplete",
        "unsupported_statement_reported_formatted",
        "unsupported_statement_modified",
        "supported_statement_reported_unsupported",
    ),
}


RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def schema_semantics_preserved(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def formatting_is_idempotent(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def comments_preserved(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def line_width_contract(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def explicit_unsupported_handling(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
