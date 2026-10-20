from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from openai import BadRequestError, OpenAI

from .config import OpenAIClientConfig


class ContextWindowExceededError(RuntimeError):
    def __init__(self, message: str):
        super().__init__(message)
        self.usage: dict[str, int] = {}


class ContentFilterExhaustedError(ContextWindowExceededError):
    pass


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Completion:
    content: str
    tool_calls: tuple[ToolCall, ...]
    assistant_message: Mapping[str, Any]
    usage: Mapping[str, int]
    finish_reason: str | None


class OpenAIChatCompletionsClient:
    def __init__(self, config: OpenAIClientConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key(),
            base_url=config.base_url,
            timeout=180.0,
            max_retries=2,
        )

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] = (),
        *,
        require_tool: bool = False,
    ) -> Completion:
        request = dict(self.config.parameters)
        request.update(model=self.config.model, messages=list(messages))
        if tools:
            request["tools"] = list(tools)
            request.setdefault("tool_choice", "required" if require_tool else "auto")
        usage: dict[str, int] = {}
        for attempt in range(3):
            usage["model_calls"] = usage.get("model_calls", 0) + 1
            try:
                response = self.client.chat.completions.create(**request)
            except BadRequestError as exc:
                code = str(getattr(exc, "code", "") or "").lower()
                message = str(exc).lower()
                if code == "context_length_exceeded" or any(
                    s in message
                    for s in (
                        "maximum context length",
                        "context window exceeded",
                        "context length exceeded",
                    )
                ):
                    error = ContextWindowExceededError(
                        "The model context window was exceeded."
                    )
                    error.usage = usage
                    raise error from None
                if code in {"content_filter", "content_policy_violation"}:
                    continue
                raise
            raw_usage = response.usage.model_dump() if response.usage else {}
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage[key] = usage.get(key, 0) + int(raw_usage.get(key, 0) or 0)
            if not response.choices:
                raise RuntimeError("The API returned no completion choices.")
            choice = response.choices[0]
            if choice.finish_reason == "content_filter":
                continue
            message = choice.message
            calls = tuple(
                ToolCall(c.id, c.function.name, c.function.arguments)
                for c in message.tool_calls or ()
            )
            assistant: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }
            if calls:
                assistant["tool_calls"] = [
                    {
                        "id": c.call_id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.arguments},
                    }
                    for c in calls
                ]
            reasoning = getattr(message, "reasoning_content", None)
            if reasoning is not None:
                assistant["reasoning_content"] = reasoning
            return Completion(
                message.content or "", calls, assistant, usage, choice.finish_reason
            )
        error = ContentFilterExhaustedError(
            "Content filtering persisted after three attempts."
        )
        error.usage = usage
        raise error
