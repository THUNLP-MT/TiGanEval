from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .plugins import PluginError, load_symbol
from .protocol import RubricResult


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    "What an evaluator may know about the submission it is judging."

    task_id: str
    rubric_id: str
    run_id: str
    config: Mapping[str, Any] = field(default_factory=dict)
    private_state: Mapping[str, Any] = field(default_factory=dict)
    submission: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RubricSpec:
    rubric_id: str
    evaluator: str
    priority: int


@dataclass(frozen=True, slots=True)
class LoadedRubric:
    spec: RubricSpec
    evaluator: Any

    def evaluate(self, artifact_dir: Path, context: EvaluationContext) -> RubricResult:
        target = getattr(self.evaluator, "evaluate", self.evaluator)
        if not callable(target):
            raise PluginError(
                f"rubric {self.spec.rubric_id!r} evaluator is not callable"
            )
        result = target(artifact_dir, context)
        if not isinstance(result, RubricResult):
            raise PluginError(
                f"rubric {self.spec.rubric_id!r} evaluator must return RubricResult, "
                f"got {type(result).__name__}"
            )
        if result.rubric_id != self.spec.rubric_id:
            raise PluginError(
                f"rubric evaluator returned id {result.rubric_id!r}; expected {self.spec.rubric_id!r}"
            )
        if not result.passed and not result.failure_mode:
            raise PluginError(
                f"rubric {self.spec.rubric_id!r} failed without a failure_mode"
            )
        return result


def load_rubrics(
    entries: Sequence[Mapping[str, Any]], base_dir: Path
) -> tuple[LoadedRubric, ...]:
    "Resolve the manifest's rubric entries to callable evaluators, in order."

    loaded: list[LoadedRubric] = []
    seen: set[str] = set()
    for entry in entries:
        rubric_id = str(entry.get("id", "")).strip()
        reference = str(entry.get("evaluator", "")).strip()
        if not rubric_id or not reference:
            raise PluginError("each rubric requires id and evaluator")
        if rubric_id in seen:
            raise PluginError(f"duplicate rubric id: {rubric_id}")
        seen.add(rubric_id)
        spec = RubricSpec(
            rubric_id=rubric_id,
            evaluator=reference,
            priority=int(entry.get("priority", 0)),
        )
        loaded.append(
            LoadedRubric(spec=spec, evaluator=load_symbol(reference, base_dir))
        )
    return tuple(loaded)
