from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class OpenAIClientConfig:
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> OpenAIClientConfig:
        unknown = set(value) - {"model", "api_key_env", "base_url", "parameters"}
        if unknown:
            raise ValueError(f"Unknown model settings: {sorted(unknown)}")
        model = str(value.get("model", "")).strip()
        if not model:
            raise ValueError("A model name is required.")
        parameters = value.get("parameters") or {}
        if not isinstance(parameters, Mapping):
            raise ValueError("parameters must be a mapping of API request parameters.")
        reserved = {"model", "messages", "tools", "stream", "n"} & parameters.keys()
        if reserved:
            raise ValueError(f"Cannot override request fields: {sorted(reserved)}")
        return cls(
            model,
            str(value.get("api_key_env", "OPENAI_API_KEY")),
            value.get("base_url") or os.environ.get("OPENAI_BASE_URL") or None,
            dict(parameters),
        )

    def api_key(self) -> str:
        value = os.environ.get(self.api_key_env, "").strip()
        if not value:
            raise ValueError(f"Set {self.api_key_env} before running the evaluation.")
        return value


@dataclass(frozen=True)
class UserConfig:
    client: OpenAIClientConfig
