"""The five binary project checks for the one-tap reorder watch."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, FAILURE_MODES, evaluate_project

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    name: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for name, modes in FAILURE_MODES.items()
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def base_lift(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def collection_account(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def lift_interval(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def stop_or_continue_plan(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def drop_ramp_invariance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
