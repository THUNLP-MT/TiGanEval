"""The rule report the console prints and the nightly roll-up reads.

One row per rule definition of the decision it belongs to: how many times that
body ran, how many of those runs came back with a value, and how many times a
reference to its rule was answered from the value the decision already had.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import Definition, RuleStat, definition_id, package_of, success_rate


def new_profile() -> dict[str, RuleStat]:
    """A report for one decision and nothing else."""

    return {}


def stats(profile: Any) -> Mapping[str, RuleStat]:
    return dict(profile or {})


def _row(profile: Any, definition: Definition) -> RuleStat:
    return profile.setdefault(definition_id(definition), RuleStat())


def count_eval(profile: Any, definition: Definition) -> None:
    _row(profile, definition).evals += 1


def count_success(profile: Any, definition: Definition) -> None:
    _row(profile, definition).successes += 1


def count_reuse(profile: Any, definition: Definition) -> None:
    _row(profile, definition).reuse += 1


def _add(bucket: RuleStat, stat: RuleStat) -> None:
    bucket.evals += int(stat.evals)
    bucket.successes += int(stat.successes)
    bucket.reuse += int(stat.reuse)


def package_totals(profile: Any) -> Mapping[str, RuleStat]:
    """One bucket per package, each definition counted into exactly one."""

    totals: dict[str, RuleStat] = {}
    for key, stat in stats(profile).items():
        _add(totals.setdefault(package_of(key), RuleStat()), stat)
    return totals


def merge(left: Any, right: Any) -> dict[str, RuleStat]:
    """Sum two reports into a new one that shares no row with either side."""

    merged: dict[str, RuleStat] = {}
    for source in (left, right):
        for key, stat in stats(source).items():
            _add(merged.setdefault(key, RuleStat()), stat)
    return merged


def rate(stat: RuleStat) -> float:
    return success_rate(getattr(stat, "evals", 0), getattr(stat, "successes", 0))
