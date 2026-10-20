"Minimal linear ReAct Agent: append-only history, one tool-call batch per turn."

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Sequence

from tiganeval.client import (
    ContentFilterExhaustedError,
    ContextWindowExceededError,
    OpenAIChatCompletionsClient,
)
from tiganeval.prompts import build_agent_system_prompt
from tiganeval.protocol import Action, AgentTurn, Event, EventKind, ToolDefinition

LOGGER = logging.getLogger(__name__)


_MAX_COMPLETION_ATTEMPTS = 3


class AgentProtocolError(RuntimeError):
    "A model response could not be interpreted as one Agent action batch."

    def __init__(
        self,
        message: str,
        diagnostics: Mapping[str, Any],
        *,
        usage: Mapping[str, int] | None = None,
    ):
        super().__init__(message)
        self.diagnostics = dict(diagnostics)
        self.usage = dict(usage or {})


def _content_preview(content: str, limit: int = 300) -> str:
    collapsed = " ".join(content.split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit] + "…"


def _merge_usage(*values: Mapping[str, Any]) -> dict[str, int]:
    keys = {key for usage in values for key in usage}
    return {key: sum(int(usage.get(key, 0) or 0) for usage in values) for key in keys}


class ReActAgent:
    "Append typed events, query the model, and return its tool-call batch."

    build_system_prompt = staticmethod(build_agent_system_prompt)

    def __init__(self, client: OpenAIChatCompletionsClient):
        self.client = client
        self.messages: list[Mapping[str, Any]] = []
        self.tools: tuple[ToolDefinition, ...] = ()
        self.pending_tool_call_ids: tuple[str, ...] = ()

    def reset(self, system_prompt: str, tools: Sequence[ToolDefinition]) -> None:
        self.messages = [{"role": "system", "content": system_prompt}]
        self.tools = tuple(tools)
        self.pending_tool_call_ids = ()

    def _append_events(self, events: Sequence[Event]) -> None:
        for event in events:
            if event.tool_call_id:
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": event.tool_call_id,
                        "content": (
                            "The requested user interaction completed and produced a follow-up user instruction."
                            if event.kind is EventKind.INSTRUCTION
                            else event.content
                        ),
                    }
                )
                if event.kind is EventKind.INSTRUCTION:
                    self.messages.append(
                        {
                            "role": "user",
                            "content": f"Project instruction from {event.source}:\n\n{event.content}",
                        }
                    )
            else:
                self.messages.append(
                    {
                        "role": "user",
                        "content": f"Project {event.kind.value} from {event.source}:\n\n{event.content}",
                    }
                )

    def _check_tool_results(self, events: Sequence[Event]) -> None:
        result_ids = tuple(
            event.tool_call_id for event in events if event.tool_call_id is not None
        )
        diagnostics = {
            "tool_call_count": len(events),
            "tool_call_names": [],
            "content_preview": "",
        }
        if self.pending_tool_call_ids:
            if (
                len(result_ids) != len(events)
                or result_ids != self.pending_tool_call_ids
            ):
                raise AgentProtocolError(
                    "tool-result events must match every pending tool_call_id exactly once",
                    diagnostics,
                )
        elif result_ids:
            raise AgentProtocolError(
                "received tool-result events without pending tool calls",
                diagnostics,
            )

    def _complete(self) -> tuple[Any, dict[str, int]]:
        "Query the model until it returns a tool call, retrying empty completions."

        tools = [tool.as_openai_tool() for tool in self.tools]
        usage_parts: list[dict[str, int]] = []
        for attempt in range(1, _MAX_COMPLETION_ATTEMPTS + 1):
            try:
                turn = self.client.complete(self.messages, tools, require_tool=True)
            except (ContentFilterExhaustedError, ContextWindowExceededError) as exc:
                exc.usage = _merge_usage(*usage_parts, exc.usage)
                raise
            usage = dict(turn.usage)
            usage["model_calls"] = int(usage.get("model_calls", 1) or 1)
            usage_parts.append(usage)
            if turn.tool_calls:
                return turn, _merge_usage(*usage_parts)
            LOGGER.debug(
                "empty completion attempt %d/%d: finish_reason=%r content_preview=%r",
                attempt,
                _MAX_COMPLETION_ATTEMPTS,
                turn.finish_reason,
                _content_preview(turn.content),
            )
        diagnostics = {
            "finish_reason": turn.finish_reason,
            "tool_call_count": 0,
            "tool_call_names": [],
            "content_preview": _content_preview(turn.content),
            "attempts": _MAX_COMPLETION_ATTEMPTS,
        }
        raise AgentProtocolError(
            "expected at least one tool call after "
            f"{_MAX_COMPLETION_ATTEMPTS} attempts; "
            f"finish_reason={turn.finish_reason!r}, "
            "tool_call_count=0, tool_call_names=[], "
            f"content_preview={diagnostics['content_preview']!r}",
            diagnostics,
            usage=_merge_usage(*usage_parts),
        )

    def step(self, events: Sequence[Event]) -> AgentTurn:
        if not events:
            raise ValueError("ReAct Agent requires at least one project event")
        self._check_tool_results(events)
        self._append_events(events)
        self.pending_tool_call_ids = ()
        turn, usage = self._complete()
        self.messages.append(turn.assistant_message)
        actions: list[Action] = []
        for call in turn.tool_calls:
            diagnostics = {
                "finish_reason": turn.finish_reason,
                "tool_call_count": len(turn.tool_calls),
                "tool_call_names": [item.name for item in turn.tool_calls],
                "content_preview": _content_preview(turn.content),
                "reason": "invalid_tool_arguments",
            }
            try:
                arguments = json.loads(call.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise AgentProtocolError(
                    f"invalid JSON arguments for tool {call.name!r}",
                    diagnostics,
                    usage=usage,
                ) from exc
            if not isinstance(arguments, Mapping):
                raise AgentProtocolError(
                    f"tool {call.name!r} arguments must be a JSON object",
                    diagnostics,
                    usage=usage,
                )
            actions.append(
                Action(
                    name=call.name,
                    arguments=dict(arguments),
                    tool_call_id=call.call_id,
                )
            )
        self.pending_tool_call_ids = tuple(call.call_id for call in turn.tool_calls)
        return AgentTurn(actions=tuple(actions), thought=turn.content, usage=usage)
