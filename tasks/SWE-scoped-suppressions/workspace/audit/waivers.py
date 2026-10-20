"""Waiver resolution for the estate audit: the inline `# waive` form.

A reviewer silences one finding by writing `# waive` on the line it is
reported at, with an optional list of rule ids or rule names after it. The
pass below reads those comments and takes the findings they name out of the
weekly report, counting each waiver it read.
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
    for line in document.lines:
        found = directive_on(line)
        if found is None or found[0] != "waive":
            continue
        rules = selected_rules(found[1], profile)
        waived[line.number] = rules
        if rules:
            by_rule += 1
        else:
            blanket += 1
    reported = []
    for finding in baseline_findings(document, profile):
        rules = waived.get(finding.line)
        if rules is None or (rules and finding.rule_id not in rules):
            reported.append(finding)
    return Report(
        findings=tuple(reported),
        counters=Counters(reported=len(reported), blanket=blanket, by_rule=by_rule),
    )
