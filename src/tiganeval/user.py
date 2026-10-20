from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .client import OpenAIChatCompletionsClient
from .config import UserConfig
from .prompts import load_prompt
from .protocol import Event, EventKind, FeedbackSelection


class UserSimulator:
    def __init__(self, registry, config: UserConfig):
        self.registry = registry
        self.client = OpenAIChatCompletionsClient(config.client)
        self._past_messages: list[str] = []

    def start_episode(
        self,
        *,
        condition_id: str,
        initial_instruction: str,
        owner_knowledge: str,
        editable_paths: Sequence[str],
    ) -> None:
        if not initial_instruction.strip() or not owner_knowledge.strip():
            raise ValueError(
                "Initial instruction and user knowledge must be non-empty."
            )
        surface = (
            "The engineer can only change these files: "
            + ", ".join(editable_paths)
            + "."
            if editable_paths
            else "The engineer can only change files inside the project workspace."
        )
        self._system_prompt = load_prompt(
            "user", persona=self.registry.user_persona, editable_surface=surface
        )
        self._owner_knowledge = owner_knowledge
        self._past_messages = [initial_instruction]

    def feedback(self, selection: FeedbackSelection) -> Event:
        _, observation = self.registry.select(
            selection.rubric_id,
            selection.failure_mode,
            selection.occurrence,
            observed=selection.observed,
        )
        return self._generate("What you just observed:", observation)

    def answer(self, agent_message: str) -> Event:
        message = agent_message.strip()
        if not message:
            raise ValueError("A user question must be non-empty.")
        return self._generate(
            "What the engineer just sent you (a claim, not something you observed):",
            {"source": "agent_message", "message": message},
        )

    def _generate(self, heading: str, observation: Mapping[str, Any]) -> Event:
        if not self._past_messages:
            raise ValueError("Start the episode before requesting a user message.")
        prompt = (
            "What you know about the project:\n\n"
            f"{self._owner_knowledge}\n\n"
            "What you have already told the engineer:\n\n"
            f"{_render_observation(self._past_messages)}\n\n"
            f"{heading}\n\n{_render_observation(observation)}"
        )
        turn = self.client.complete(
            [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        message = turn.content.strip()
        if turn.tool_calls or not message:
            raise ValueError("The simulated user must return a non-empty text message.")
        self._past_messages.append(message)
        return Event(
            EventKind.INSTRUCTION, message, "user", {"usage": dict(turn.usage)}
        )


def _render_observation(value: Any, *, indent: int = 0) -> str:
    "Render task-controlled evidence without escaping semantic newlines."

    prefix = " " * indent
    if isinstance(value, Mapping):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (Mapping, list, tuple)):
                lines.append(f"{prefix}{key}:")
                lines.append(_render_observation(item, indent=indent + 2))
            elif isinstance(item, str) and "\n" in item:
                lines.append(f"{prefix}{key}:")
                lines.extend(
                    f"{' ' * (indent + 2)}{line}" for line in item.splitlines()
                )
            else:
                rendered = (
                    item
                    if isinstance(item, str)
                    else json.dumps(item, ensure_ascii=False, default=str)
                )
                lines.append(f"{prefix}{key}: {rendered}")
        return "\n".join(lines)
    if isinstance(value, (list, tuple)):
        lines = []
        for item in value:
            rendered = _render_observation(item, indent=indent + 2)
            rendered_lines = rendered.splitlines() or [""]
            lines.append(f"{prefix}- {rendered_lines[0].lstrip()}")
            lines.extend(rendered_lines[1:])
        return "\n".join(lines)
    if isinstance(value, str):
        return "\n".join(f"{prefix}{line}" for line in value.splitlines())
    return f"{prefix}{json.dumps(value, ensure_ascii=False, default=str)}"
