"The five binary project checks for the ticket-triage misroute review."

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


def intake_misroute_estimate(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def purchase_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def misroute_range_is_honest(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def reviewer_regime_invariance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_purchase_order(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
