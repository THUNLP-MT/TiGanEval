"""The estate's frozen policy-audit contract.

Every platform in the estate reads its service policy through this module, so
the document model, the rule table, the profiles and the shape of a weekly
report are the same wherever the audit runs. `waivers.py` is the only part of
the pass a platform team writes for itself.

A policy document is indented text. A line ending in a colon whose deeper
lines are list items is one entry whose value is those items; a line ending in
a colon whose deeper lines are keys is a block; anything else with a colon is
an entry with its value written on the line. Every entry is a unit, and a unit
carries one span of lines, one dotted path, and the value elements the rule
table is applied to. Blocks carry the path and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping


BLANK, COMMENT, BLOCK, ENTRY, ITEM = "blank", "comment", "block", "entry", "item"


# --------------------------------------------------------------------------
# The document model


@dataclass(frozen=True, slots=True)
class Line:
    """One physical line: its body, its trailing comment, its indentation."""
    number: int
    text: str
    content: str
    comment: str
    indent: int
    kind: str

@dataclass(frozen=True, slots=True)
class Element:
    """One value of a unit, and the line the estate reads it on."""
    line: int
    text: str

@dataclass(frozen=True, slots=True)
class Unit:
    """One entry of a policy document.

    ``start_line`` and ``end_line`` are the first and last physical lines the
    entry occupies; an entry written on one line has them equal, and an entry
    whose value is a list of items runs from its key line to its last item.
    """
    index: int
    key: str
    path: str
    start_line: int
    end_line: int
    depth: int
    elements: tuple[Element, ...]


@dataclass(frozen=True, slots=True)
class Document:
    name: str
    lines: tuple[Line, ...]
    units: tuple[Unit, ...]

    def line(self, number: int) -> Line | None:
        index = int(number) - 1
        return self.lines[index] if 0 <= index < len(self.lines) else None

    def unit(self, index: int) -> Unit | None:
        number = int(index)
        return self.units[number] if 0 <= number < len(self.units) else None


def split_comment(text: str) -> tuple[str, str]:
    """One line as its body and its comment; the comment keeps its ``#``."""
    body, marker, rest = str(text).partition("#")
    return body.rstrip(), f"{marker}{rest}".strip()


def _unquote(text: str) -> str:
    value = str(text).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _elements(number: int, value: str) -> tuple[Element, ...]:
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        parts = [part for part in inner.split(",")] if inner else []
    else:
        parts = [text] if text else []
    return tuple(Element(line=number, text=_unquote(part)) for part in parts if part.strip())


def _classify(raw: str) -> tuple[str, str, str, int]:
    content, comment = split_comment(raw)
    stripped = content.strip()
    indent = len(content) - len(content.lstrip(" "))
    if not stripped:
        kind = COMMENT if comment else BLANK
        indent = len(raw) - len(raw.lstrip(" ")) if comment else 0
    elif stripped.startswith("- "):
        kind = ITEM
    else:
        kind = ENTRY
    return content, comment, kind, indent


def parse_document(text: str, name: str = "") -> Document:
    """Split one policy document into its lines and its units."""
    rows: list[Line] = []
    for number, raw in enumerate(str(text).splitlines(), start=1):
        content, comment, kind, indent = _classify(raw)
        rows.append(Line(number, raw, content, comment, indent, kind))

    def next_content(start: int) -> Line | None:
        for row in rows[start:]:
            if row.kind not in (BLANK, COMMENT):
                return row
        return None

    lines: list[Line] = []
    units: list[Unit] = []
    stack: list[tuple[int, str]] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        if row.kind in (BLANK, COMMENT, ITEM):
            lines.append(row)
            index += 1
            continue
        stripped = row.content.strip()
        key, _, value = stripped.partition(":")
        key = key.strip()
        following = next_content(index + 1)
        deeper = following is not None and following.indent > row.indent
        if not value.strip() and deeper and following is not None and following.kind != ITEM:
            lines.append(replace(row, kind=BLOCK))
            while stack and row.indent <= stack[-1][0]:
                stack.pop()
            stack.append((row.indent, key))
            index += 1
            continue
        while stack and row.indent <= stack[-1][0]:
            stack.pop()
        lines.append(row)
        start_line = end_line = row.number
        elements: list[Element] = []
        if value.strip():
            elements.extend(_elements(row.number, value))
            index += 1
        else:
            index += 1
            while index < len(rows):
                nxt = rows[index]
                if nxt.kind in (BLANK, COMMENT):
                    lines.append(nxt)
                    index += 1
                    continue
                if nxt.kind == ITEM and nxt.indent > row.indent:
                    lines.append(nxt)
                    elements.append(Element(nxt.number, _unquote(nxt.content.strip()[2:])))
                    end_line = nxt.number
                    index += 1
                    continue
                break
        path = ".".join([block for _, block in stack] + [key])
        units.append(Unit(len(units), key, path, start_line, end_line,
                          row.indent, tuple(elements)))
    lines.sort(key=lambda item: item.number)
    return Document(name=str(name), lines=tuple(lines), units=tuple(units))


def unit_span(document: Document, index: int) -> tuple[int, int]:
    """The first and last physical line of one unit."""
    unit = document.unit(index)
    if unit is None:
        raise IndexError(f"no unit {index} in {document.name!r}")
    return unit.start_line, unit.end_line


def unit_of_line(document: Document, number: int) -> int | None:
    """The unit whose span holds this line, if any."""
    for unit in document.units:
        if unit.start_line <= int(number) <= unit.end_line:
            return unit.index
    return None


def next_unit_after(document: Document, number: int) -> int | None:
    """The first unit that starts below this line."""
    for unit in document.units:
        if unit.start_line > int(number):
            return unit.index
    return None


# --------------------------------------------------------------------------
# The rule table, the profiles, and the selector vocabulary


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    name: str
    summary: str


RULES: tuple[Rule, ...] = (
    Rule("SEC-SHELL-EXEC", "shell_exec", "a value hands work to a shell"),
    Rule("SEC-NET-OPEN", "open_network", "the service shares the node's network"),
    Rule("SEC-SECRET-PLAIN", "plain_secret", "a secret is written in the document"),
    Rule("SEC-PORT-ADMIN", "admin_port", "an administrative port is published"),
    Rule("SEC-IMAGE-FLOAT", "floating_image", "the image is a moving tag"),
    Rule("OPS-RESTART-NEVER", "no_restart", "the service is never restarted"),
    Rule("OPS-LOG-OFF", "logging_off", "the service writes no log"),
)

#: Which rules each estate run has switched on. The weekly report runs
#: `release`; the platforms the estate is retiring are read under `hardening`.
PROFILES: Mapping[str, tuple[str, ...]] = {
    "release": tuple(rule.id for rule in RULES),
    "hardening": tuple(rule.id for rule in RULES if rule.id.startswith("SEC-")),
}

_BY_ID = {rule.id: rule for rule in RULES}
_BY_NAME = {rule.name: rule for rule in RULES}


@dataclass(frozen=True, slots=True)
class Profile:
    """How one estate run is configured.

    ``ignore_waivers`` is the flag the quarterly reconciliation run sets.
    """
    name: str = "release"
    ignore_waivers: bool = False


def enabled_rules(profile: Profile) -> tuple[str, ...]:
    """The rule ids switched on for this run, in table order."""
    return PROFILES.get(str(profile.name), ())


def rule_of(rule_id: str) -> Rule | None:
    return _BY_ID.get(str(rule_id))

def resolve_selector(token: str, profile: Profile) -> tuple[str, ...]:
    """The enabled rule ids one written token names.

    A token is an exact rule id, a rule name, a prefix ending in ``*``, or the
    word ``all``. Anything else names nothing here and comes back empty, and
    so does a token whose rule this run has not switched on.
    """
    text = str(token).strip()
    enabled = enabled_rules(profile)
    if not text:
        return ()
    if text == "all":
        return tuple(enabled)
    if text.endswith("*"):
        prefix = text[:-1]
        return tuple(rule_id for rule_id in enabled if rule_id.startswith(prefix))
    if text in enabled:
        return (text,)
    rule = _BY_NAME.get(text)
    if rule is not None and rule.id in enabled:
        return (rule.id,)
    return ()


# --------------------------------------------------------------------------
# The detector and the report shape


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the rule table objects to, at the line the estate reads it on."""
    rule_id: str
    unit: int
    line: int
    path: str
    value: str


_SECRET_SUFFIXES = ("_token", "_password", "_secret", "_key")
_ADMIN_PORTS = ("22", "2375", "5900")


def _hits(rule_id: str, unit: Unit, element: Element) -> bool:
    key, value = unit.key, element.text
    if rule_id == "SEC-SHELL-EXEC":
        return "sh -c" in value or "| sh" in value
    if rule_id == "SEC-NET-OPEN":
        if key in ("network", "network_mode"):
            return value == "host"
        return key in ("allow_from", "ingress") and value in ("0.0.0.0/0", "::/0")
    if rule_id == "SEC-SECRET-PLAIN":
        return key.endswith(_SECRET_SUFFIXES) and not value.startswith("vault:")
    if rule_id == "SEC-PORT-ADMIN":
        return key in ("ports", "expose") and value in _ADMIN_PORTS
    if rule_id == "SEC-IMAGE-FLOAT":
        return key == "image" and value.endswith(":latest")
    if rule_id == "OPS-RESTART-NEVER":
        return key == "restart" and value == "never"
    if rule_id == "OPS-LOG-OFF":
        return key == "logging" and value == "off"
    return False


def baseline_findings(document: Document, profile: Profile) -> tuple[Finding, ...]:
    """Everything the rule table objects to in this document, waivers aside."""
    enabled = enabled_rules(profile)
    found: list[Finding] = []
    for unit in document.units:
        for element in unit.elements:
            for rule_id in enabled:
                if _hits(rule_id, unit, element):
                    found.append(Finding(rule_id, unit.index, element.line,
                                         unit.path, element.text))
    return tuple(sorted(found, key=lambda item: (item.line, item.rule_id, item.unit)))


@dataclass(frozen=True, slots=True)
class Counters:
    """The three numbers the estate review signs off for one document."""
    reported: int = 0
    blanket: int = 0
    by_rule: int = 0

@dataclass(frozen=True, slots=True)
class Report:
    """What one run of the audit produces for one document."""
    findings: tuple[Finding, ...] = ()
    counters: Counters = Counters()
