"""Turning a stored rule into the reminder times we send.

The prototype in here works out the absolute reading a series starts at once,
when the rule is first read, and then steps forward by a fixed amount for every
following occurrence. Rendering back into the customer's zone happens at the
end, when the reminder text is written.
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
    offset_in_force,
)

#: Nothing the product sells recurs more often than this in one query.
STEP_LIMIT = 4000


def start_instant(spec: RuleSpec) -> datetime:
    """The absolute reading the series begins at."""

    offset = offset_in_force(spec.wall_start, spec.zone)
    return spec.wall_start - timedelta(seconds=offset)


def expand(spec: RuleSpec, window: Window) -> list[datetime]:
    """The absolute readings this rule fires at inside `window`, ascending."""

    step = PERIOD_STEP[spec.period] * spec.interval
    opens = from_utc(window.start, spec.zone)
    closes = from_utc(window.end, spec.zone)
    instant = start_instant(spec)
    produced: list[datetime] = []
    for index in range(STEP_LIMIT):
        if spec.count is not None and index >= spec.count:
            break
        if spec.until is not None and instant >= spec.until:
            break
        reading = from_utc(instant, spec.zone)
        if opens <= reading < closes:
            produced.append(instant)
        instant += step
    return produced


def serialize(spec: RuleSpec) -> str:
    """The rule written out as text for the feeds and the mobile export."""

    repeat = f"REPEAT:{spec.period};EVERY={spec.interval}"
    if spec.count is not None:
        repeat = f"{repeat};TIMES={spec.count}"
    else:
        repeat = f"{repeat};ENDS={format_stamp(from_utc(spec.until, spec.zone))}"
    return "\n".join(
        [
            f"SERIES:{spec.summary}",
            f"BEGINS:{format_stamp(start_instant(spec))}Z",
            repeat,
        ]
    )


def merge_feeds(specs: Sequence[RuleSpec], window: Window) -> list[datetime]:
    """The reminder times for one meeting the user holds through several feeds."""

    seen: dict[str, datetime] = {}
    for spec in specs:
        for instant in expand(spec, window):
            label = f"{spec.zone}|{from_utc(instant, spec.zone).isoformat()}"
            seen.setdefault(label, instant)
    return sorted(seen.values())
