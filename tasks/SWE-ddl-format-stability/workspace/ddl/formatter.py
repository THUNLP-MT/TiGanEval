"""Formatting migration DDL.

The current formatter breaks a statement at its commas and indents what follows.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import FormatOptions, split_statements


def format_statement(statement: str, options: FormatOptions) -> str:
    head, _, rest = statement.partition("(")
    body, _, tail = rest.rpartition(")")
    pad = " " * options.indent
    parts = [part.strip() for part in body.split(",")]
    lines = [f"{' '.join(head.split())} ("]
    lines.extend(f"{pad}{part}," for part in parts[:-1])
    if parts:
        lines.append(f"{pad}{parts[-1]}")
    lines.append(f"){' '.join(tail.split())}")
    return "\n".join(lines)


def format_statements(text: str, options: FormatOptions) -> Mapping[str, Any]:
    """Format every statement in a migration file."""

    rows: list[dict[str, Any]] = []
    formatted: list[str] = []
    for index, statement in enumerate(split_statements(text)):
        formatted.append(format_statement(statement, options))
        rows.append({"index": index, "status": "formatted"})
    return {"formatted": "\n\n".join(formatted), "statements": rows}
