from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

JsonObject = dict[str, Any]


class EventKind(StrEnum):
    INSTRUCTION = "instruction"
    OBSERVATION = "observation"


@dataclass(frozen=True, slots=True)
class Event:
    kind: EventKind
    content: str
    source: str
    data: Mapping[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None

    def to_dict(self) -> JsonObject:
        return {
            "kind": self.kind.value,
            "content": self.content,
            "source": self.source,
            "data": dict(self.data),
            "tool_call_id": self.tool_call_id,
        }


@dataclass(frozen=True, slots=True)
class Action:
    "One tool call selected by an Agent."

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None

    def to_dict(self) -> JsonObject:
        return {
            "name": self.name,
            "arguments": dict(self.arguments),
            "tool_call_id": self.tool_call_id,
        }


@dataclass(frozen=True, slots=True)
class AgentTurn:
    "All tool calls emitted by one model response."

    actions: tuple[Action, ...]
    thought: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "thought": self.thought,
            "usage": dict(self.usage),
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: Mapping[str, Any]

    def as_openai_tool(self) -> JsonObject:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": dict(self.parameters),
            },
        }


@dataclass(frozen=True, slots=True)
class RubricResult:
    "One binary rubric judgement; ``failure_mode`` names why it failed."

    rubric_id: str
    passed: bool
    failure_mode: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return 1.0 if self.passed else 0.0

    def to_dict(self) -> JsonObject:
        return {
            "rubric_id": self.rubric_id,
            "passed": self.passed,
            "score": self.score,
            "failure_mode": self.failure_mode,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class FeedbackSelection:
    "The failed rubric and Observation chosen after a rejected submission."

    rubric_id: str
    failure_mode: str
    occurrence: int
    observation_id: str
    stalled: bool

    observed: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        return {
            "rubric_id": self.rubric_id,
            "failure_mode": self.failure_mode,
            "occurrence": self.occurrence,
            "observation_id": self.observation_id,
            "stalled": self.stalled,
            "observed": dict(self.observed),
        }
