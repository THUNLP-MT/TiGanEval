"""Five binary project rubrics for the streaming JSON reader."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import (
    BUCKETS,
    CORRECTNESS_PRIORITY,
    ENCODING_PRIORITY,
    FLOW_PRIORITY,
    FRAMING_PRIORITY,
    LIFECYCLE_PRIORITY,
    evaluate_project,
)

_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "chunking_invariant_value_stream": CORRECTNESS_PRIORITY,
    "explicit_framing_rejection": FRAMING_PRIORITY,
    "encoding_contract_fidelity": ENCODING_PRIORITY,
    "bounded_stream_buffering": FLOW_PRIORITY,
    "stream_lifecycle_discipline": LIFECYCLE_PRIORITY,
}
FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    rubric_id: ("candidate_execution_failed", *modes)
    for rubric_id, modes in _PRIORITY.items()
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def chunking_invariant_value_stream(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def explicit_framing_rejection(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def encoding_contract_fidelity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def bounded_stream_buffering(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def stream_lifecycle_discipline(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
