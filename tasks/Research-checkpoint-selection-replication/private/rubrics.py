"""The five binary project checks for the ranking release readout."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Sequence
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import CANDIDATE_FAILURE, EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, CURRENT_CAMPAIGN, FAILURE_MODES, evaluate_project

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for rubric_id, modes in FAILURE_MODES.items()
}


class _ReportsFromTheCampaignSheCanOpen(RubricSet):
    """Pick the incident to describe from August whenever it has one."""

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
                item for item in failures if item.get("campaign_id") == CURRENT_CAMPAIGN
            ]
            if here:
                return super().select_mode(rubric_id, analysis, here)
        return super().select_mode(rubric_id, analysis, failures)


RUBRICS = _ReportsFromTheCampaignSheCanOpen(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def shipped_gain_within_tolerance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def range_covers_and_meets_floor(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def gain_invariant_to_lot_and_turn(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def booking_reads_shortlist_on_one_lot(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_reconciles_receipts(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
