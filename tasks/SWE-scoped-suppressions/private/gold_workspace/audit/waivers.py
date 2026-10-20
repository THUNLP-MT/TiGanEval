"""Waiver resolution for the estate audit: inline, region, and next-entry forms.

A waiver is written as a comment and resolved onto the entry the audit reports
at, so what it covers does not depend on where the value happened to be
written. Everything covering one entry is combined before a finding is
classified, and one finding leaves exactly one mark on the counters.
"""

from __future__ import annotations

import re

from .contract import (
    BLANK,
    Counters,
    Document,
    Profile,
    Report,
    baseline_findings,
    next_unit_after,
    resolve_selector,
    unit_of_line,
)


_DIRECTIVE = re.compile(r"^#\s*(waive[a-z-]*)\b(.*)$", re.IGNORECASE)

#: What one waiver says: everything here, or these rules here.
BLANKET = None


def directive_on(line) -> tuple[str, str] | None:
    """The waiver keyword and the selector text written on one line."""

    match = _DIRECTIVE.match(line.comment)
    if match is None:
        return None
    return match.group(1).lower(), match.group(2).strip()


def selected_rules(selector: str, profile: Profile) -> tuple[str, ...]:
    """The rule ids a selector names, in the order the tokens were written."""

    ids: list[str] = []
    for token in re.split(r"[\s,]+", str(selector).strip()):
        if token:
            ids.extend(resolve_selector(token, profile))
    return tuple(dict.fromkeys(ids))


def _reach(selector: str, profile: Profile) -> frozenset[str] | None:
    """What a waiver reaches: BLANKET when nothing was written after it.

    A selector somebody wrote but this run cannot place names no rule, so it
    reaches nothing at all; it never widens into everything.
    """

    if not str(selector).strip():
        return BLANKET
    return frozenset(selected_rules(selector, profile))


def _combine(reaches) -> frozenset[str] | None:
    """Everything covering one entry, read together."""

    combined: frozenset[str] = frozenset()
    for reach in reaches:
        if reach is BLANKET:
            return BLANKET
        combined |= reach
    return combined


def resolve_coverage(document: Document, profile: Profile) -> dict:
    """What each entry of the document is covered by, entry index to waivers."""

    per_line: dict = {}
    per_unit: dict = {}
    regions: list[tuple[int, frozenset[str] | None]] = []

    def add(store: dict, key, reach) -> None:
        if key is not None:
            store.setdefault(key, []).append(reach)

    for line in document.lines:
        if line.kind != BLANK:
            while regions and line.indent < regions[-1][0]:
                regions.pop()
        found = directive_on(line)
        keyword, selector = found if found is not None else ("", "")
        if keyword == "waive-end" and regions:
            regions.pop()
        for _, reach in regions:
            add(per_line, line.number, reach)
        if keyword == "waive-begin":
            regions.append((line.indent, _reach(selector, profile)))
        elif keyword == "waive":
            add(per_line, line.number, _reach(selector, profile))
        elif keyword == "waive-next":
            add(per_unit, next_unit_after(document, line.number), _reach(selector, profile))

    for number, reaches in per_line.items():
        add(per_unit, unit_of_line(document, number), _combine(reaches))
    return per_unit


def build_report(document: Document, profile: Profile) -> Report:
    """The weekly report for one document: what is open, and what was waived."""

    baseline = baseline_findings(document, profile)
    if profile.ignore_waivers:
        return Report(findings=baseline, counters=Counters(reported=len(baseline)))
    coverage = resolve_coverage(document, profile)
    reported = []
    blanket = by_rule = 0
    for finding in baseline:
        reach = _combine(coverage.get(finding.unit, []))
        if reach is BLANKET:
            blanket += 1
        elif finding.rule_id in reach:
            by_rule += 1
        else:
            reported.append(finding)
    return Report(
        findings=tuple(reported),
        counters=Counters(reported=len(reported), blanket=blanket, by_rule=by_rule),
    )
