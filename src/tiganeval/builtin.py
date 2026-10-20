from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Mapping

_RUNNER_STATE_DIRECTORY = ".tiganeval"


def ask_user_tool() -> Mapping[str, Any]:
    return {
        "name": "ask_user",
        "kind": "user",
        "description": (
            "Ask the project owner a question or tell them something. They "
            "answer from what they know about the project. Call this tool alone."
        ),
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        },
    }


def submit_tool() -> Mapping[str, Any]:
    return {
        "name": "submit",
        "kind": "submit",
        "description": (
            "Deliver the current workspace to the project owner for a formal "
            "review. The owner reports the next instruction. Call this tool alone."
        ),
        "parameters": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        },
    }


def _safe_workspace_path(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes workspace: {relative}")
    return target


def _reject_runner_state(path: Path, workspace: Path) -> None:
    "Keep runtime-owned state outside the Agent-visible file surface."

    relative = path.relative_to(workspace.resolve())
    if _RUNNER_STATE_DIRECTORY in relative.parts:
        raise ValueError(f"path belongs to runner-owned state: {relative.as_posix()}")


def _allowed_path(path: Path, workspace: Path, config: Mapping[str, Any]) -> None:
    patterns = config.get("allowed_paths")
    if not patterns:
        return
    relative = path.relative_to(workspace.resolve()).as_posix()
    if not any(fnmatch.fnmatch(relative, str(pattern)) for pattern in patterns):
        raise ValueError(f"path is outside the editable surface: {relative}")


def _workspace_relative(path: Path, workspace: Path) -> str:
    "Return a stable relative path even when /var resolves to /private/var."

    return path.relative_to(workspace.resolve()).as_posix()


def write_text(arguments: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
    path = _safe_workspace_path(context.workspace, str(arguments["path"]))
    _reject_runner_state(path, context.workspace)
    _allowed_path(path, context.workspace, context.config)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = str(arguments.get("content", ""))
    path.write_text(content, encoding="utf-8")
    return {
        "path": _workspace_relative(path, context.workspace),
        "bytes": len(content.encode("utf-8")),
    }


def read_text(arguments: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
    path = _safe_workspace_path(context.workspace, str(arguments["path"]))
    _reject_runner_state(path, context.workspace)
    content = path.read_text(encoding="utf-8")
    max_chars = int(context.config.get("max_chars", 30_000))
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]
    return {
        "path": _workspace_relative(path, context.workspace),
        "content": content,
        "truncated": truncated,
    }


def list_files(arguments: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
    relative = str(arguments.get("path", "."))
    root = _safe_workspace_path(context.workspace, relative)
    if not root.is_dir():
        raise ValueError(f"not a directory: {relative}")
    ignored = {
        ".git",
        _RUNNER_STATE_DIRECTORY,
        ".venv",
        "__pycache__",
        ".pytest_cache",
    }
    limit = int(context.config.get("max_files", 500))
    workspace = context.workspace.resolve()
    files = [
        path.relative_to(workspace).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in ignored for part in path.relative_to(workspace).parts)
    ]
    return {"files": files[:limit], "truncated": len(files) > limit}


def replace_text(arguments: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
    path = _safe_workspace_path(context.workspace, str(arguments["path"]))
    _reject_runner_state(path, context.workspace)
    _allowed_path(path, context.workspace, context.config)
    old = str(arguments["old"])
    new = str(arguments.get("new", ""))
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    expected = int(arguments.get("expected_replacements", 1))
    if count != expected:
        raise ValueError(f"expected {expected} exact matches, found {count}")
    path.write_text(content.replace(old, new), encoding="utf-8")
    return {
        "path": _workspace_relative(path, context.workspace),
        "replacements": count,
    }
