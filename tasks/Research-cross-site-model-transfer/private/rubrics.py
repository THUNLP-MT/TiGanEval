"""The five binary project checks for the Brookfield triage report."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Sequence
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import CANDIDATE_FAILURE, EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, CURRENT_DEPLOYMENT, FAILURE_MODES, evaluate_project

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for rubric_id, modes in FAILURE_MODES.items()
}


class _ReportsFromTheCentreSheCanOpen(RubricSet):
    """Pick the incident to describe from Brookfield whenever it has one."""

    def select_mode(
        self,
        rubric_id: str,
        analysis: Mapping[str, Any],
        failures: Sequence[Mapping[str, Any]],
    ) -> str:
        stopped = any(
            (str(item.get("kind", "")) == CANDIDATE_FAILURE for item in failures)
        )
        if not analysis.get("harness_error") and (not stopped):
            here = [
                item
                for item in failures
                if item.get("deployment") == CURRENT_DEPLOYMENT
            ]
            if here:
                return super().select_mode(rubric_id, analysis, here)
        return super().select_mode(rubric_id, analysis, failures)


RUBRICS = _ReportsFromTheCentreSheCanOpen(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def served_stream_error(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def published_error_range(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_built_from_the_intake_counters(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_review_request(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def reviews_reconcile_with_the_ledger(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
