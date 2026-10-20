"""The pricing rule grammar: tokens, nodes, and the parser.

The whole rule language of `pricing/rulebook.json` is parsed here, including
the two recovery forms, so nothing downstream has to read rule source. This
file ships with the rating release alongside `protocol.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class Node:
    """One node of a compiled rule expression.

    `kind` is `number`, `text`, `call`, `binary`, `region`, `body`, `fallback`
    or `cleanup`. A `region` carries `{"retry": bool, "guard": str | None}` in
    `value` and `(body, fallback | None, cleanup | None)` in `children`; each
    wrapper holds one child, and the engine counts one attempt against the
    order every time it enters a `body`."""
    kind: str
    value: Any = None
    children: tuple[Any, ...] = ()


_PUNCTUATION = ("(", ")", "{", "}", ",", "+", "*")
_WORDS = ("rescue", "retry", "otherwise", "always")


def tokenize(source: str) -> list[tuple[str, Any]]:
    """Split rule source into (kind, value) tokens: num, text, word, punct."""
    tokens: list[tuple[str, Any]] = []
    text, index = str(source), 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char == '"':
            end = text.index('"', index + 1)
            tokens.append(("text", text[index + 1 : end]))
            index = end + 1
        elif char.isdigit() or (char == "." and text[index + 1 : index + 2].isdigit()):
            end = index
            while end < len(text) and (text[end].isdigit() or text[end] == "."):
                end += 1
            tokens.append(("num", float(text[index:end])))
            index = end
        elif char.isalpha() or char == "_":
            end = index
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(("word", text[index:end]))
            index = end
        elif char in _PUNCTUATION:
            tokens.append(("punct", char))
            index += 1
        else:
            raise ValueError(f"rule source has an unreadable character {char!r}")
    return tokens


class _Parser:
    """Recursive descent over the whole rule grammar."""
    def __init__(self, tokens: Sequence[tuple[str, Any]]):
        self.tokens, self.at = list(tokens), 0
    def peek(self) -> tuple[str, Any]:
        return self.tokens[self.at] if self.at < len(self.tokens) else ("end", None)
    def take(self, kind: str | None = None, value: Any = None) -> tuple[str, Any]:
        token = self.peek()
        if (kind and token[0] != kind) or (value and token[1] != value):
            raise ValueError(f"expected {value or kind}, found {token[1]!r}")
        self.at += 1
        return token
    def accept(self, kind: str, value: Any) -> bool:
        if self.peek() == (kind, value):
            self.at += 1
            return True
        return False
    def expression(self) -> Node:
        node = self.term()
        while self.accept("punct", "+"):
            node = Node("binary", "+", (node, self.term()))
        return node
    def term(self) -> Node:
        node = self.primary()
        while self.accept("punct", "*"):
            node = Node("binary", "*", (node, self.primary()))
        return node
    def block(self) -> Node:
        self.take("punct", "{")
        node = self.expression()
        self.take("punct", "}")
        return node
    def rescue(self) -> Node:
        """`rescue(body, fallback)`, or a block with `otherwise` and `always`."""
        if self.accept("punct", "("):
            body = self.expression()
            self.take("punct", ",")
            fallback = self.expression()
            self.take("punct", ")")
            return region(body, fallback, retry=False, guard=None, cleanup=None)
        retries = self.accept("word", "retry")
        body, fallback, guard, cleanup = self.block(), None, None, None
        if self.accept("word", "otherwise"):
            if self.peek()[0] == "text":
                guard = str(self.take()[1])
            fallback = self.block()
        if self.accept("word", "always"):
            cleanup = self.block()
        return region(body, fallback, retry=retries, guard=guard, cleanup=cleanup)
    def primary(self) -> Node:
        kind, value = self.take()
        if kind in ("num", "text"):
            return Node("number" if kind == "num" else "text", value)
        if (kind, value) == ("punct", "("):
            node = self.expression()
            self.take("punct", ")")
            return node
        if (kind, value) == ("word", "rescue"):
            return self.rescue()
        if kind == "word" and value not in _WORDS:
            self.take("punct", "(")
            arguments: list[Node] = []
            if not self.accept("punct", ")"):
                arguments.append(self.expression())
                while self.accept("punct", ","):
                    arguments.append(self.expression())
                self.take("punct", ")")
            return Node("call", str(value), tuple(arguments))
        raise ValueError(f"a rule expression cannot start with {value!r}")


def parse(source: str) -> Node:
    """Compile one rule expression to a node tree."""
    parser = _Parser(tokenize(source))
    node = parser.expression()
    if parser.peek()[0] != "end":
        raise ValueError(f"trailing rule source at {parser.peek()[1]!r}")
    return node


def region(body: Node, fallback: Node | None, *, retry: bool, guard: str | None,
           cleanup: Node | None) -> Node:
    """A recovery region around `body`, with the wrappers the engine counts."""
    return Node("region", {"retry": bool(retry), "guard": guard}, (
        Node("body", None, (body,)),
        None if fallback is None else Node("fallback", None, (fallback,)),
        None if cleanup is None else Node("cleanup", None, (cleanup,))))
