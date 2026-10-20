"""Waiver resolution for the estate audit: inline, region, and next-line forms.

A reviewer silences one finding by writing `# waive` on the line it is
reported at. `# waive-begin` marks every line down to `# waive-end`, and
`# waive-next` marks the line after it; all three take the same list of rule
ids or rule names after the keyword.
"""

from __future__ import annotations

import re

from .contract import (
    Counters,
    Document,
    Profile,
    Report,
    baseline_findings,
    resolve_selector,
)


_DIRECTIVE = re.compile(r"^#\s*(waive[a-z-]*)\b(.*)$", re.IGNORECASE)


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


def build_report(document: Document, profile: Profile) -> Report:
    """The weekly report for one document: what is open, and what was waived."""

    waived: dict[int, tuple[str, ...]] = {}
    blanket = by_rule = 0
    region: tuple[str, ...] | None = None

    def count(rules: tuple[str, ...]) -> None:
        nonlocal blanket, by_rule
        if rules:
            by_rule += 1
        else:
            blanket += 1

    for line in document.lines:
        found = directive_on(line)
        if found is not None:
            keyword, selector = found
            rules = selected_rules(selector, profile)
            if keyword == "waive-begin":
                region = rules
                count(rules)
                continue
            if keyword == "waive-end":
                region = None
                continue
            if keyword == "waive-next":
                waived[line.number + 1] = rules
                count(rules)
                continue
            if keyword == "waive":
                waived[line.number] = rules
                count(rules)
                continue
        if region is not None:
            waived[line.number] = region

    reported = []
    for finding in baseline_findings(document, profile):
        rules = waived.get(finding.line)
        if rules is None or (rules and finding.rule_id not in rules):
            reported.append(finding)
    return Report(
        findings=tuple(reported),
        counters=Counters(reported=len(reported), blanket=blanket, by_rule=by_rule),
    )
