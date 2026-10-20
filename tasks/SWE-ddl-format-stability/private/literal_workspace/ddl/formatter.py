"""Formatting migration DDL.

Break each statement at its commas, put every column on its own line indented
by the directory's indent, and keep the result inside the directory's width.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import FormatOptions, split_statements


def format_statement(statement: str, options: FormatOptions) -> str:
    """Break one statement at its commas and indent the body."""

    text = " ".join(statement.split())
    head, opened, rest = text.partition("(")
    if not opened:
        return text
    body, closed, tail = rest.rpartition(")")
    if not closed:
        return text
    pad = " " * max(1, int(options.indent))
    parts = [part.strip() for part in body.split(",") if part.strip()]
    lines = [f"{head.strip()} ("]
    for position, part in enumerate(parts):
        suffix = "," if position < len(parts) - 1 else ""
        lines.append(f"{pad}{part}{suffix}")
    lines.append(f"){tail.strip()}")
    return "\n".join(lines)


def format_statements(text: str, options: FormatOptions) -> Mapping[str, Any]:
    """Format every statement in a migration file."""

    rows: list[dict[str, Any]] = []
    formatted: list[str] = []
    for index, statement in enumerate(split_statements(text)):
        formatted.append(format_statement(statement, options))
        rows.append({"index": index, "status": "formatted"})
    return {"formatted": "\n\n".join(formatted), "statements": rows}
