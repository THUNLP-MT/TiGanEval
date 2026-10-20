"""The five binary project checks for the Halstow dispatch board."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Sequence
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import CANDIDATE_FAILURE, EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, CURRENT_DEPOT, FAILURE_MODES, evaluate_project

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for rubric_id, modes in FAILURE_MODES.items()
}


class _ReportsFromTheDepotSheCanOpen(RubricSet):
    """Pick the incident to describe from Halstow whenever it has one."""

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
            here = [item for item in failures if item.get("depot") == CURRENT_DEPOT]
            if here:
                return super().select_mode(rubric_id, analysis, here)
        return super().select_mode(rubric_id, analysis, failures)


RUBRICS = _ReportsFromTheDepotSheCanOpen(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def stream_rate_within_tolerance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def class_windows_hold_and_meet_floor(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def windows_invariant_to_pull_and_drop(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_visit_feasible_and_reaches_the_unsheeted_class(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_reconciles_receipts(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
