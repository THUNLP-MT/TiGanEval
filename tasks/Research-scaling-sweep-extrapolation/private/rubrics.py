"The five binary project checks for the scaling sweep readout."

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


def ten_times_loss_prediction(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def runs_accounted_for(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def loss_interval_is_honest(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_run_booking(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def prediction_holds_across_the_queue(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
