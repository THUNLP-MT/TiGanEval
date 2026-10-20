"""Formatting migration DDL without changing what a statement means."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .protocol import (
    INLINE_CONSTRAINT_STARTS,
    POST_BODY_KEYWORDS,
    TABLE_CONSTRAINT_STARTS,
    DdlError,
    FormatOptions,
    Token,
    parse_schema,
    split_statements,
    tokenize,
)


def _render(tokens: Sequence[Token]) -> str:
    """Join a token run with the spacing the project's canonical form uses."""

    parts: list[str] = []
    for index, token in enumerate(tokens):
        text = token.text.casefold() if token.kind == "word" else token.text
        if not parts:
            parts.append(text)
            continue
        previous = tokens[index - 1]
        no_space_before = text in {",", ")", "]", ";", ".", ">"} or (text == "<" and previous.kind == "word") or (
            text == "(" and previous.kind == "word" and previous.text.casefold() not in {"check", "key", "unique", "exists"}
        )
        no_space_after = previous.text in {"(", "[", ".", "<"}
        parts.append(text if no_space_before or no_space_after else " " + text)
    return "".join(parts)


def _split_top_level(tokens: Sequence[Token]) -> list[list[Token]]:
    groups: list[list[Token]] = []
    current: list[Token] = []
    depth = 0
    for token in tokens:
        if token.kind == "punct" and token.text in "([<":
            depth += 1
        elif token.kind == "punct" and token.text in ")]>":
            depth = max(0, depth - 1)
        if token.kind == "punct" and token.text == "," and depth == 0:
            groups.append(current)
            current = []
            continue
        current.append(token)
    if current:
        groups.append(current)
    return groups


def _emit_comments(pending: list[Token], indent: str, lines: list[str]) -> None:
    """Put each comment on its own line so it can never swallow code."""

    for token in pending:
        text = " ".join(token.text.split()) if token.text.startswith("/*") else token.text.rstrip()
        lines.append(f"{indent}{text}")
    pending.clear()


def _partition(tokens: Sequence[Token]) -> tuple[list[Token], list[Token], list[Token]]:
    """Split a statement into head, body groups, and the trailing clauses."""

    depth = 0
    body_start = body_end = None
    for index, token in enumerate(tokens):
        if token.kind == "punct" and token.text == "(":
            depth += 1
            if depth == 1 and body_start is None:
                body_start = index
        elif token.kind == "punct" and token.text == ")":
            depth -= 1
            if depth == 0 and body_start is not None:
                body_end = index
                break
    if body_start is None or body_end is None:
        raise DdlError("the table body is never closed")
    return list(tokens[:body_start]), list(tokens[body_start + 1 : body_end]), list(tokens[body_end + 1 :])


def format_statement(statement: str, options: FormatOptions) -> str:
    """Format one supported statement. Comments keep their order and lines."""

    tokens = list(tokenize(statement))
    head, body, tail = _partition(tokens)
    pad = " " * max(1, int(options.indent))
    lines: list[str] = []
    pending: list[Token] = []

    head_code = [token for token in head if token.kind != "comment"]
    _emit_comments([token for token in head if token.kind == "comment"], "", lines)
    lines.append(f"{_render(head_code)} (")

    groups = [group for group in _split_top_level(body) if any(t.kind != "comment" for t in group) or group]
    rendered: list[tuple[list[Token], str]] = []
    for group in groups:
        code = [token for token in group if token.kind != "comment"]
        if not code:
            pending.extend(token for token in group if token.kind == "comment")
            continue
        rendered.append(([token for token in group if token.kind == "comment"], _render(code)))

    for position, (group_comments, text) in enumerate(rendered):
        _emit_comments(pending + group_comments, pad, lines)
        suffix = "," if position < len(rendered) - 1 else ""
        lines.append(f"{pad}{text}{suffix}")

    tail_code = [token for token in tail if token.kind != "comment" and token.text != ";"]
    _emit_comments(pending + [token for token in tail if token.kind == "comment"], "", lines)
    lines.append(")")
    for clause in _split_clauses(tail_code):
        lines.append(_render(clause))
    lines.append(";")
    return "\n".join(lines)


def _split_clauses(tokens: Sequence[Token]) -> list[list[Token]]:
    clauses: list[list[Token]] = []
    current: list[Token] = []
    for token in tokens:
        if token.kind == "word" and token.lowered in POST_BODY_KEYWORDS and current:
            clauses.append(current)
            current = []
        current.append(token)
    if current:
        clauses.append(current)
    return clauses


def format_statements(text: str, options: FormatOptions) -> Mapping[str, Any]:
    """Format every supported statement and pass the rest through untouched."""

    rows: list[dict[str, Any]] = []
    pieces: list[str] = []
    for index, statement in enumerate(split_statements(text)):
        supported = parse_schema(statement) is not None
        if not supported:
            rows.append(
                {
                    "index": index,
                    "status": "unsupported",
                    "reason": "only CREATE TABLE with a column body is formatted",
                }
            )
            pieces.append(statement.strip())
            continue
        try:
            pieces.append(format_statement(statement, options))
            rows.append({"index": index, "status": "formatted"})
        except DdlError as exc:
            rows.append({"index": index, "status": "unsupported", "reason": str(exc)})
            pieces.append(statement.strip())
    return {"formatted": "\n\n".join(pieces), "statements": rows}
