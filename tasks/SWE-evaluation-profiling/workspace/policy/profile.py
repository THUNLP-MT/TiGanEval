"""Dana's first cut at the rule report, from section 3 of the draft."""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import RuleStat

COUNTS: dict[str, RuleStat] = {}  # how often each rule has been looked up


def new_profile() -> Any:
    return COUNTS


def record(profile: Any, path: str, succeeded: bool) -> None:
    stat = COUNTS.setdefault(str(path).rsplit(".", 1)[-1], RuleStat())
    stat.evals += 1
    if succeeded:
        stat.successes += 1


def stats(profile: Any) -> Mapping[str, RuleStat]:
    return profile


def package_totals(profile: Any) -> Mapping[str, RuleStat]:
    totals: dict[str, RuleStat] = {}
    for name, stat in stats(profile).items():
        bucket = totals.setdefault(name, RuleStat())
        bucket.evals += stat.evals
        bucket.successes += stat.successes
    return totals


def merge(left: Any, right: Any) -> Any:
    merged = dict(stats(left))
    merged.update(stats(right))
    return merged


def rate(stat: RuleStat) -> float:
    return stat.successes / stat.evals
