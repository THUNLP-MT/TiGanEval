"""The rule report: how often each rule ran and how often it came back with a value."""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import RuleStat, success_rate

COUNTS: dict[str, RuleStat] = {}


def new_profile() -> Any:
    return COUNTS


def record(profile: Any, path: str, succeeded: bool) -> None:
    stat = COUNTS.setdefault(str(path).rsplit(".", 1)[-1], RuleStat())
    stat.evals += 1
    if succeeded:
        stat.successes += 1


def stats(profile: Any) -> Mapping[str, RuleStat]:
    return dict(profile or {})


def package_totals(profile: Any) -> Mapping[str, RuleStat]:
    totals: dict[str, RuleStat] = {}
    for name, stat in stats(profile).items():
        bucket = totals.setdefault(name, RuleStat())
        bucket.evals += stat.evals
        bucket.successes += stat.successes
    return totals


def merge(left: Any, right: Any) -> Any:
    merged = dict(stats(left))
    for key, stat in stats(right).items():
        if key in merged:
            merged[key].evals += stat.evals
            merged[key].successes += stat.successes
        else:
            merged[key] = stat
    return merged


def rate(stat: RuleStat) -> float:
    return success_rate(stat.evals, stat.successes)
