"""Turning a stored rule into the reminder times we send.

A rule is written in wall-clock terms, so the series is walked in wall-clock
terms: the date and time of day move by the rule's period, and each reading is
turned into an absolute reading on its own, against the offset the zone is
using on that date. Everything downstream — selection, merging, paging —
compares absolute readings, because that is the only axis that is monotone
across a change of offset.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from .protocol import (
    PERIOD_STEP,
    RuleSpec,
    Window,
    format_stamp,
    local_offsets,
    to_utc,
    zone_for,
)

STEP_LIMIT = 4000


def resolve(wall: datetime, zone: str) -> datetime:
    """The absolute reading a wall-clock reading in `zone` really happens at.

    One offset in force is the plain case. Two means the zone arrived at this
    reading twice, and the occurrence is the first of them, so the reminder is
    sent once and at the earlier arrival. None means the zone stepped over this
    reading; the occurrence still belongs to the series, and starting from the
    offset that was in force before the step puts it the length of the step
    later on the clock.
    """

    offsets = local_offsets(wall, zone)
    if len(offsets) == 1:
        return to_utc(wall, zone, offsets[0])
    if len(offsets) > 1:
        return to_utc(wall, zone, max(offsets))
    return to_utc(wall, zone, min(zone_for(zone).offsets))


def occurrences(spec: RuleSpec, horizon: datetime | None = None) -> list[datetime]:
    """The series' absolute readings, ascending, up to `horizon`.

    A day and a week are both longer than any change of offset the zone table
    holds, so the absolute readings only ever move forward. Once a wall-clock
    reading is late enough that even its earliest possible absolute reading is
    at or after `horizon`, everything left in the series is past it and none of
    it has to be resolved. That is what lets one week of a meeting a customer
    has booked out for years be answered at all: the series carries on past the
    end of the zone table, and the table refuses a reading it has no entry for,
    so an engine that resolves the whole series before answering asks the table
    about dates nobody asked about and comes back with nothing for a week it
    had everything it needed to answer.
    """

    step = PERIOD_STEP[spec.period] * spec.interval
    latest = (
        None if horizon is None
        else horizon + timedelta(seconds=max(zone_for(spec.zone).offsets))
    )
    wall = spec.wall_start
    produced: list[datetime] = []
    for index in range(STEP_LIMIT):
        if spec.count is not None and index >= spec.count:
            break
        if latest is not None and wall >= latest:
            break
        instant = resolve(wall, spec.zone)
        if spec.until is not None and instant >= spec.until:
            break
        produced.append(instant)
        wall += step
    return produced


def expand(spec: RuleSpec, window: Window) -> list[datetime]:
    """The absolute readings this rule fires at inside `window`, ascending."""

    return [instant for instant in occurrences(spec, window.end) if window.contains(instant)]


def serialize(spec: RuleSpec) -> str:
    """The rule written out as text for the feeds and the mobile export.

    The start is a time of day and carries its zone; the end of the series is a
    moment and is written as one, so neither is read back as the other.
    """

    if spec.zone == "UTC":
        begins = f"BEGINS:{format_stamp(spec.wall_start)}Z"
    else:
        begins = f"BEGINS;ZONE={spec.zone}:{format_stamp(spec.wall_start)}"
    repeat = f"REPEAT:{spec.period};EVERY={spec.interval}"
    if spec.count is not None:
        repeat = f"{repeat};TIMES={spec.count}"
    else:
        repeat = f"{repeat};ENDS={format_stamp(spec.until)}Z"
    return "\n".join([f"SERIES:{spec.summary}", begins, repeat])


def merge_feeds(specs: Sequence[RuleSpec], window: Window) -> list[datetime]:
    """The reminder times for one meeting the user holds through several feeds.

    Two feeds may spell the same meeting in different zones, so the reminder a
    user receives is identified by the absolute reading it fires at and by
    nothing else.
    """

    times: set[datetime] = set()
    for spec in specs:
        times.update(expand(spec, window))
    return sorted(times)
