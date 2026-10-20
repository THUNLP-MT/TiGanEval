from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .plugins import PluginError, load_symbol
from .protocol import ToolDefinition


class EnvironmentInfrastructureError(RuntimeError):
    "A tool environment could not run or recover reliably."


@dataclass(frozen=True, slots=True)
class ToolContext:
    task_id: str
    run_id: str
    workspace: Path
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaskToolResult:
    "A handler result whose Agent-visible text and structured data differ."

    content: str
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LoadedTool:
    definition: ToolDefinition
    handler: Any | None
    config: Mapping[str, Any]
    kind: str = "tool"

    def run(self, arguments: Mapping[str, Any], context: ToolContext) -> Any:
        if self.handler is None:
            raise PluginError(
                f"environment action {self.definition.name!r} must be handled by the runner"
            )
        target = self.handler.run if hasattr(self.handler, "run") else self.handler
        if not callable(target):
            raise PluginError(f"tool {self.definition.name!r} plugin is not callable")
        return target(dict(arguments), context)


def load_tools(
    entries: Sequence[Mapping[str, Any]], base_dir: Path
) -> tuple[LoadedTool, ...]:
    loaded: list[LoadedTool] = []
    names: set[str] = set()
    for entry in entries:
        name = str(entry.get("name", "")).strip()
        kind = str(entry.get("kind", "tool")).strip()
        reference = str(entry.get("plugin", "")).strip()
        handler = entry.get("handler")
        if not name:
            raise PluginError("each action requires a name")
        if kind == "tool" and not reference and handler is None:
            raise PluginError(f"ordinary action {name!r} requires a handler")
        if kind not in {"tool", "user", "submit"}:
            raise PluginError(f"unknown action kind for {name!r}: {kind!r}")
        if name in names:
            raise PluginError(f"duplicate tool name: {name}")
        names.add(name)
        parameters = entry.get(
            "parameters", {"type": "object", "additionalProperties": True}
        )
        if not isinstance(parameters, Mapping):
            raise PluginError(f"tool {name!r} parameters must be a JSON-schema mapping")
        config = entry.get("config", {})
        if not isinstance(config, Mapping):
            raise PluginError(f"tool {name!r} config must be a mapping")
        loaded.append(
            LoadedTool(
                definition=ToolDefinition(
                    name=name,
                    description=str(entry.get("description", name)),
                    parameters=dict(parameters),
                ),
                handler=(load_symbol(reference, base_dir) if reference else handler),
                config=dict(config),
                kind=kind,
            )
        )
    return tuple(loaded)


def load_task_actions(reference: str, task_dir: Path) -> tuple[LoadedTool, ...]:
    "Load all action declarations from one task-owned Python factory."

    factory = load_symbol(reference, task_dir)
    if not callable(factory):
        raise PluginError(f"task actions factory is not callable: {reference}")
    entries = factory()
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise PluginError("task actions factory must return a sequence of mappings")
    normalized: list[Mapping[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise PluginError("every task action declaration must be a mapping")
        normalized.append(entry)
    return load_tools(normalized, task_dir)


def serialize_tool_result(value: Any) -> tuple[str, Mapping[str, Any]]:
    if isinstance(value, str):
        return value, {"result": value}
    if isinstance(value, Mapping):
        data = dict(value)
        return json.dumps(data, ensure_ascii=False, default=str), data
    if value is None:
        return "Tool completed.", {"result": None}
    data = {"result": value}
    return json.dumps(data, ensure_ascii=False, default=str), data


def serialize_task_tool_result(value: Any) -> tuple[str, Mapping[str, Any]]:
    "Serialize a task handler result into Agent-visible text and trace data."

    if not isinstance(value, TaskToolResult):
        return serialize_tool_result(value)
    if not isinstance(value.data, Mapping):
        raise TypeError("TaskToolResult.data must be a mapping")
    return str(value.content) or "Tool completed.", dict(value.data)
