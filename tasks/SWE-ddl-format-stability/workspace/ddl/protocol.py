"""Runtime contract for the migration-formatter project.

The tokenizer and the schema parser below are the frozen part of the project.
`parse_schema` is the authoritative reading of a statement: two texts mean the
same schema exactly when it returns equal values for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Iterable, Mapping, Sequence


LINE_WIDTH = 88
INDENT = 4

#: Fields every formatter report must contain.
REPORT_FIELDS = ("formatted", "statements")
STATEMENT_FIELDS = ("index", "status")
STATUSES = ("formatted", "unsupported")

KEYWORDS = frozenset(
    """
    create table if not exists primary key foreign references unique check
    not null default constraint on delete cascade restrict set partition by
    cluster options as select like int integer bigint smallint text varchar
    char boolean bool date timestamp numeric decimal float double array struct
    string bytes json and or in between is
    """.split()
)
INLINE_CONSTRAINT_STARTS = frozenset(
    {"not", "null", "default", "references", "constraint", "check", "primary", "unique"}
)
TABLE_CONSTRAINT_STARTS = frozenset({"primary", "foreign", "unique", "check", "constraint"})
POST_BODY_KEYWORDS = ("partition", "cluster", "options")


class DdlError(Exception):
    """The statement cannot be read as DDL this project supports."""


@dataclass(frozen=True, slots=True)
class Token:
    kind: str  # word | number | string | comment | punct
    text: str
    start: int

    @property
    def lowered(self) -> str:
        return self.text.casefold()


_TOKEN = re.compile(
    r"""
    (?P<comment>--[^\n]*|/\*.*?\*/)
  | (?P<string>'(?:[^']|'')*')
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<word>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<punct>[(),;.\[\]<>=+\-*/])
  | (?P<space>\s+)
    """,
    re.X | re.S,
)


def tokenize(text: str) -> tuple[Token, ...]:
    """Split DDL text into tokens, keeping comments and dropping whitespace."""

    tokens: list[Token] = []
    position = 0
    source = str(text)
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            raise DdlError(f"unreadable character at position {position}: {source[position]!r}")
        position = match.end()
        kind = match.lastgroup or ""
        if kind == "space":
            continue
        tokens.append(Token(kind=kind, text=match.group(), start=match.start()))
    return tuple(tokens)


def split_statements(text: str) -> tuple[str, ...]:
    """Split a migration file into statements on top-level semicolons."""

    statements: list[str] = []
    depth = 0
    start = 0
    source = str(text)
    for token in tokenize(source):
        if token.kind != "punct":
            continue
        if token.text == "(":
            depth += 1
        elif token.text == ")":
            depth -= 1
        elif token.text == ";" and depth == 0:
            statements.append(source[start : token.start + 1])
            start = token.start + 1
    tail = source[start:]
    if tail.strip():
        statements.append(tail)
    return tuple(statement for statement in statements if statement.strip())


def comments(text: str) -> tuple[str, ...]:
    """Every comment in the text, in order, normalised for whitespace."""

    return tuple(
        " ".join(token.text.split()) for token in tokenize(text) if token.kind == "comment"
    )


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type_name: str
    constraints: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True, slots=True)
class Schema:
    table_name: str
    if_not_exists: bool
    columns: tuple[Column, ...]
    table_constraints: tuple[str, ...]
    post_body: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "if_not_exists": self.if_not_exists,
            "columns": [column.as_dict() for column in self.columns],
            "table_constraints": list(self.table_constraints),
            "post_body": list(self.post_body),
        }


def _normalise(tokens: Sequence[Token]) -> str:
    """Canonical text for a token run: unquoted words lowered, spacing fixed."""

    parts: list[str] = []
    for index, token in enumerate(tokens):
        text = token.text
        # Unquoted words are case-insensitive in this dialect; only the
        # contents of a string literal carry case.
        if token.kind == "word":
            text = text.casefold()
        if not parts:
            parts.append(text)
            continue
        previous = tokens[index - 1]
        tight = (
            text in {",", ")", "(", "]", "[", ".", ">"} or (text == "<" and previous.kind == "word")
            and not (text == "(" and previous.kind == "punct" and previous.text == ",")
        ) or previous.text in {"(", "[", ".", "<"}
        parts.append(text if tight else " " + text)
    return "".join(parts).replace("( ", "(").replace(" )", ")")


def _split_top_level(tokens: Sequence[Token]) -> list[list[Token]]:
    groups: list[list[Token]] = []
    current: list[Token] = []
    depth = 0
    for token in tokens:
        # Angle brackets nest parameterised types such as struct<a int, b string>.
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


def parse_schema(statement: str) -> Schema | None:
    """Read one statement as a schema, or return None if it is not supported.

    This is the authoritative reading: two statements describe the same schema
    exactly when this function returns equal values for them.
    """

    tokens = [token for token in tokenize(statement) if token.kind != "comment"]
    words = [token.lowered for token in tokens]
    if words[:2] != ["create", "table"]:
        return None
    cursor = 2
    if_not_exists = words[cursor : cursor + 3] == ["if", "not", "exists"]
    if if_not_exists:
        cursor += 3
    name_parts: list[str] = []
    while cursor < len(tokens) and not (tokens[cursor].kind == "punct" and tokens[cursor].text == "("):
        name_parts.append(tokens[cursor].lowered if tokens[cursor].kind == "word" else tokens[cursor].text)
        cursor += 1
    if cursor >= len(tokens):
        return None
    table_name = "".join(name_parts)
    if not table_name:
        return None
    # `CREATE TABLE ... AS SELECT` and `... LIKE ...` are out of scope.
    if any(word in {"as", "select", "like"} for word in words[:cursor]):
        return None

    depth = 0
    body_start = cursor
    body_end = None
    for index in range(cursor, len(tokens)):
        token = tokens[index]
        if token.kind == "punct" and token.text == "(":
            depth += 1
        elif token.kind == "punct" and token.text == ")":
            depth -= 1
            if depth == 0:
                body_end = index
                break
    if body_end is None:
        raise DdlError("the table body is never closed")

    columns: list[Column] = []
    constraints: list[str] = []
    for group in _split_top_level(tokens[body_start + 1 : body_end]):
        if not group:
            continue
        if group[0].lowered in TABLE_CONSTRAINT_STARTS and not (
            len(group) > 1 and group[1].kind == "word" and group[1].lowered not in KEYWORDS
        ):
            constraints.append(_normalise(group))
            continue
        name = group[0].lowered if group[0].kind == "word" else group[0].text
        split_at = len(group)
        inner = 0
        for index in range(1, len(group)):
            token = group[index]
            if token.kind == "punct" and token.text in "([<":
                inner += 1
            elif token.kind == "punct" and token.text in ")]>":
                inner = max(0, inner - 1)
            elif inner == 0 and token.kind == "word" and token.lowered in INLINE_CONSTRAINT_STARTS:
                split_at = index
                break
        type_name = _normalise(group[1:split_at])
        rest = group[split_at:]
        columns.append(
            Column(
                name=name,
                type_name=type_name,
                constraints=(_normalise(rest),) if rest else (),
            )
        )

    post_tokens = [
        token
        for token in tokens[body_end + 1 :]
        if not (token.kind == "punct" and token.text == ";")
    ]
    post_body: list[str] = []
    current: list[Token] = []
    for token in post_tokens:
        if token.kind == "word" and token.lowered in POST_BODY_KEYWORDS and current:
            post_body.append(_normalise(current))
            current = []
        current.append(token)
    if current:
        post_body.append(_normalise(current))

    return Schema(
        table_name=table_name,
        if_not_exists=if_not_exists,
        columns=tuple(columns),
        table_constraints=tuple(constraints),
        post_body=tuple(post_body),
    )


@dataclass(frozen=True, slots=True)
class FormatOptions:
    line_width: int = LINE_WIDTH
    indent: int = INDENT
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FormatOptions":
        return cls(
            line_width=int(value.get("line_width", LINE_WIDTH)),
            indent=int(value.get("indent", INDENT)),
            extra=dict(value.get("extra", {})),
        )


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def require_report(report: Any) -> Mapping[str, Any]:
    """Validate the shape of a formatter report and return it unchanged."""

    if not isinstance(report, Mapping):
        raise TypeError("format_statements must return a mapping")
    missing = [name for name in REPORT_FIELDS if name not in report]
    if missing:
        raise ValueError(f"formatter report is missing fields: {', '.join(missing)}")
    if not isinstance(report["formatted"], str):
        raise TypeError("formatter report formatted must be text")
    rows = report["statements"]
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TypeError("formatter report statements must be a sequence")
    for row in rows:
        if not isinstance(row, Mapping) or any(name not in row for name in STATEMENT_FIELDS):
            raise ValueError("each statement row needs index and status")
        if str(row["status"]) not in STATUSES:
            raise ValueError(f"statement status must be one of {STATUSES}")
    return report


__all__ = (
    "Column",
    "DdlError",
    "FormatOptions",
    "INDENT",
    "INLINE_CONSTRAINT_STARTS",
    "KEYWORDS",
    "LINE_WIDTH",
    "POST_BODY_KEYWORDS",
    "REPORT_FIELDS",
    "STATEMENT_FIELDS",
    "STATUSES",
    "Schema",
    "TABLE_CONSTRAINT_STARTS",
    "Token",
    "canonical_json",
    "comments",
    "parse_schema",
    "require_report",
    "split_statements",
    "tokenize",
)
