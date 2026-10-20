"The five binary project checks for the header apportionment."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import EXECUTION_FAILURE_MODE, RubricSet

from .harness import BUCKETS, FAILURE_MODES, evaluate_project


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    name: tuple(mode for mode in modes if mode != EXECUTION_FAILURE_MODE)
    for name, modes in FAILURE_MODES.items()
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def supply_shares_within_tolerance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def band_covers_and_meets_floor(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def shares_invariant_to_signature_shift(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_visit_identifies_mixture(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def report_reconciles_receipts(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
