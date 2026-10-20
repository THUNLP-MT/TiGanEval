"""Turning a stored rule into the reminder times we send.

The stored rule now carries the customer's zone, so the start of the series is
turned into an absolute reading against that zone instead of against ours, the
reminder text is rendered in that zone, and the exported rule says which zone
it belongs to. The series itself is still walked by stepping the absolute
reading forward one period at a time.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from .protocol import (
    PERIOD_STEP,
    RuleSpec,
    Window,
    format_stamp,
    from_utc,
    local_offsets,
    offset_in_force,
)

STEP_LIMIT = 4000


def start_instant(spec: RuleSpec) -> datetime:
    """The absolute reading the series begins at, in the customer's own zone."""

    offsets = local_offsets(spec.wall_start, spec.zone)
    offset = offsets[0] if offsets else offset_in_force(spec.wall_start, spec.zone)
    return spec.wall_start - timedelta(seconds=offset)


def occurrences(spec: RuleSpec) -> list[datetime]:
    step = PERIOD_STEP[spec.period] * spec.interval
    instant = start_instant(spec)
    produced: list[datetime] = []
    for index in range(STEP_LIMIT):
        if spec.count is not None and index >= spec.count:
            break
        if spec.until is not None and instant >= spec.until:
            break
        produced.append(instant)
        instant += step
    return produced


def expand(spec: RuleSpec, window: Window) -> list[datetime]:
    return [instant for instant in occurrences(spec) if window.contains(instant)]


def serialize(spec: RuleSpec) -> str:
    """The rule written out with the customer's zone on it."""

    if spec.zone == "UTC":
        begins = f"BEGINS:{format_stamp(spec.wall_start)}Z"
    else:
        begins = f"BEGINS;ZONE={spec.zone}:{format_stamp(spec.wall_start)}"
    repeat = f"REPEAT:{spec.period};EVERY={spec.interval}"
    if spec.count is not None:
        repeat = f"{repeat};TIMES={spec.count}"
    else:
        repeat = f"{repeat};ENDS={format_stamp(from_utc(spec.until, spec.zone))}"
    return "\n".join([f"SERIES:{spec.summary}", begins, repeat])


def merge_feeds(specs: Sequence[RuleSpec], window: Window) -> list[datetime]:
    """The reminder times for one meeting the user holds through several feeds.

    A reminder is the meeting's time of day in the zone the feed stores it in,
    so two feeds that agree on the rule are folded together.
    """

    seen: dict[tuple[str, str], datetime] = {}
    for spec in specs:
        for instant in expand(spec, window):
            seen.setdefault((spec.zone, from_utc(instant, spec.zone).isoformat()), instant)
    return sorted(seen.values())
