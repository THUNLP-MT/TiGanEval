"""The five binary project checks for the reservation-capacity quarter."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Sequence
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import CANDIDATE_FAILURE, EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, FAILURE_MODES, STUDY, evaluate_project

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    name: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for name, modes in FAILURE_MODES.items()
}


class _ReportsFromTheQuarterSheCanOpen(RubricSet):
    """Pick the incident to describe from this quarter whenever it has one."""

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
            here = [item for item in failures if item.get("study") == STUDY]
            if here:
                return super().select_mode(rubric_id, analysis, here)
        return super().select_mode(rubric_id, analysis, failures)


RUBRICS = _ReportsFromTheQuarterSheCanOpen(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def exceedance_within_tolerance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def range_covers_and_meets_floor(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_reconciles_receipts(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_run_feasible_and_informative(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def estimate_invariant_to_settling_and_lineage(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
