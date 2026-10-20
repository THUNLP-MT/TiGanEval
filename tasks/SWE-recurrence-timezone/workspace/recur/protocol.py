"""Runtime contract for the reminder schedule engine.

The zone table, the stored rule record, the window predicate and the rule-text
reader below are the fixed part of the project. The reminder dispatcher, the
mobile importer, the subscription feeds and the customer-facing calendar view
are all built against them, and they ship in that release rather than ours.
Everything here is deterministic, and the table covers a bounded range of dates
and refuses readings outside it rather than guessing an offset.

Rule text
---------

A stored rule is written out as three lines, in this order::

    SERIES:<name>
    BEGINS[;ZONE=<zone>]:<stamp>
    REPEAT:<DAILY|WEEKLY>;EVERY=<n>;(TIMES=<n>|ENDS=<stamp>)

A stamp is ``YYYYMMDDTHHMMSS``, optionally followed by ``Z``. One carrying a
``ZONE`` parameter is a wall-clock reading in that zone; one with no ``ZONE``
parameter is an absolute reading, whether or not it ends in ``Z``; one carrying
both names two zones at once and is refused. ``TIMES`` and ``ENDS`` are
alternatives and exactly one must be present.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping


class ScheduleError(RuntimeError):
    """Anything the contract refuses."""


class UnknownZone(ScheduleError):
    """No row in the zone table carries that name."""


class OutOfRange(ScheduleError):
    """The zone table says nothing about this date."""


class RuleTextError(ScheduleError):
    """Rule text the authoritative reader will not accept."""


STAMP_FORMAT = "%Y%m%dT%H%M%S"
PERIODS: tuple[str, ...] = ("DAILY", "WEEKLY")

#: How far one step of each period moves the wall-clock date.
PERIOD_STEP: Mapping[str, timedelta] = {"DAILY": timedelta(days=1), "WEEKLY": timedelta(days=7)}

TABLE_FROM = datetime(2024, 6, 1)
TABLE_UNTIL = datetime(2028, 6, 1)


@dataclass(frozen=True, slots=True)
class Zone:
    """One zone: a standing offset plus the stretches that use another one.

    ``periods`` holds half-open ``(start, end, offset)`` triples over absolute
    readings; outside every stretch the zone is at ``base_offset``. Offsets are
    whole seconds east of the absolute reading, so ``wall = instant + offset``.
    """

    name: str
    base_offset: int
    periods: tuple[tuple[datetime, datetime, int], ...] = ()

    @property
    def offsets(self) -> tuple[int, ...]:
        """Every offset this zone uses, ascending."""
        return tuple(sorted({self.base_offset, *(period[2] for period in self.periods)}))

    def offset_at(self, instant: datetime) -> int:
        """The offset in force at an absolute reading."""
        if not TABLE_FROM <= instant < TABLE_UNTIL:
            raise OutOfRange(f"{self.name} has no entry for {instant.isoformat()}")
        for start, end, offset in self.periods:
            if start <= instant < end:
                return offset
        return self.base_offset


def _zone(name: str, base: int, alternate: int = 0, *stretches: str) -> Zone:
    """One row of the table: pairs of ``start end`` readings using `alternate`."""
    def read(text: str) -> datetime:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M")

    rows = (stretch.split() for stretch in stretches)
    return Zone(name, base, tuple((read(a), read(b), alternate) for a, b in rows))


#: The zones the product sells into. Written out by hand so that the same
#: reading resolves the same way on every machine that runs this code.
ZONES: Mapping[str, Zone] = {
    zone.name: zone
    for zone in (
        _zone("UTC", 0),
        _zone(
            "Europe/Berlin", 3600, 7200,
            "2024-03-31T01:00 2024-10-27T01:00", "2025-03-30T01:00 2025-10-26T01:00",
            "2026-03-29T01:00 2026-10-25T01:00", "2027-03-28T01:00 2027-10-31T01:00",
        ),
        _zone(
            "Australia/Sydney", 36000, 39600,
            "2024-10-05T16:00 2025-04-05T16:00", "2025-10-04T16:00 2026-04-04T16:00",
            "2026-10-03T16:00 2027-04-03T16:00", "2027-10-02T16:00 2028-04-01T16:00",
        ),
        _zone("Asia/Kolkata", 19800),
        _zone(
            "Pacific/Chatham", 45900, 49500,
            "2024-09-28T14:00 2025-04-05T14:00", "2025-09-27T14:00 2026-04-04T14:00",
            "2026-09-26T14:00 2027-04-03T14:00", "2027-09-25T14:00 2028-04-01T14:00",
        ),
    )
}


def zone_for(name: str) -> Zone:
    try:
        return ZONES[str(name)]
    except KeyError:
        raise UnknownZone(f"no entry for zone {name!r}") from None


def offset_in_force(instant: datetime, zone: str) -> int:
    """The offset `zone` is using at an absolute reading."""
    return zone_for(zone).offset_at(instant)


def from_utc(instant: datetime, zone: str) -> datetime:
    """The wall-clock reading a person in `zone` sees at an absolute reading."""
    return instant + timedelta(seconds=zone_for(zone).offset_at(instant))


def to_utc(wall: datetime, zone: str, offset: int) -> datetime:
    """The absolute reading for a wall-clock reading resolved at `offset`."""
    known = zone_for(zone).offsets
    if int(offset) not in known:
        raise ScheduleError(f"{zone} never uses offset {offset}; it uses {list(known)}")
    return wall - timedelta(seconds=int(offset))


def local_offsets(wall: datetime, zone: str) -> tuple[int, ...]:
    """The offsets at which this wall-clock reading really occurs in `zone`.

    A reading in a stretch the zone skipped over has none, and one in a stretch
    the zone repeated has two. They come back ascending by offset.
    """

    entry = zone_for(zone)
    found: list[int] = []
    for offset in entry.offsets:
        instant = wall - timedelta(seconds=offset)
        if not TABLE_FROM <= instant < TABLE_UNTIL:
            raise OutOfRange(f"{entry.name} has no entry for {wall.isoformat()}")
        if entry.offset_at(instant) == offset:
            found.append(offset)
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Window:
    """A stretch of absolute readings the dispatcher asks about."""

    start: datetime
    end: datetime

    def contains(self, instant: datetime) -> bool:
        """Whether an absolute reading belongs to this stretch."""
        return self.start <= instant < self.end

    def as_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Window":
        start, end = str(value["start"]), str(value["end"])
        return cls(datetime.fromisoformat(start), datetime.fromisoformat(end))


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """One stored recurring rule, as the product keeps it. ``wall_start`` is a
    wall-clock reading in ``zone``; ``until``, when there is one, is an absolute
    reading, because the end of a series is a moment rather than a time of day.
    Exactly one of ``count`` and ``until`` is set."""

    summary: str
    zone: str
    wall_start: datetime
    period: str
    interval: int = 1
    count: int | None = None
    until: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "zone": self.zone,
            "wall_start": self.wall_start.isoformat(),
            "period": self.period,
            "interval": self.interval,
            "count": self.count,
            "until": None if self.until is None else self.until.isoformat(),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuleSpec":
        raw_until, raw_count = value.get("until"), value.get("count")
        return cls(
            summary=str(value["summary"]),
            zone=str(value["zone"]),
            wall_start=datetime.fromisoformat(str(value["wall_start"])),
            period=str(value["period"]),
            interval=int(value.get("interval", 1)),
            count=None if raw_count is None else int(raw_count),
            until=None if raw_until is None else datetime.fromisoformat(str(raw_until)),
        )


def format_stamp(value: datetime) -> str:
    """A reading as the rule text writes it, with no zone marker of any kind."""
    return value.strftime(STAMP_FORMAT)


def parse_stamp(text: str) -> datetime:
    try:
        return datetime.strptime(str(text), STAMP_FORMAT)
    except ValueError:
        raise RuleTextError(f"{text!r} is not a stamp of the form YYYYMMDDTHHMMSS") from None


def _split_parameters(head: str) -> tuple[str, dict[str, str]]:
    parts = str(head).split(";")
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            raise RuleTextError(f"{part!r} is not a NAME=VALUE parameter")
        key, _, value = part.partition("=")
        parameters[key.strip().upper()] = value.strip()
    return parts[0].strip(), parameters


def _read_value(raw: str, zone_parameter: str | None) -> tuple[datetime, str | None]:
    """One stamp as (reading, zone name); the zone is None for an absolute one."""

    text = str(raw).strip()
    marked_absolute = text.endswith("Z")
    if marked_absolute:
        text = text[:-1]
    if zone_parameter is None:
        return parse_stamp(text), None
    if marked_absolute:
        raise RuleTextError("a time value names two zones at once")
    if zone_parameter not in ZONES:
        raise RuleTextError(f"no entry for zone {zone_parameter!r}")
    return parse_stamp(text), zone_parameter


def parse_rule_text(text: str) -> RuleSpec:
    """Read stored rule text back into a rule. This is the authoritative reader.

    The mobile importer, the subscription feeds and the customer's own calendar
    application all read a series through this function, so text that does not
    come back through it unchanged is text those readers disagree with.
    """

    lines = [line for line in str(text).replace("\r\n", "\n").split("\n") if line.strip()]
    if len(lines) != 3:
        raise RuleTextError(f"rule text has {len(lines)} lines; it must have three")

    head, _, tail = lines[0].partition(":")
    if head.strip().upper() != "SERIES" or not tail.strip():
        raise RuleTextError("the first line must be SERIES:<name>")
    summary = tail.strip()

    head, _, tail = lines[1].partition(":")
    name, parameters = _split_parameters(head)
    if name.upper() != "BEGINS":
        raise RuleTextError("the second line must be BEGINS[;ZONE=<zone>]:<stamp>")
    if set(parameters) - {"ZONE"}:
        raise RuleTextError(f"BEGINS carries unknown parameters {sorted(set(parameters) - {'ZONE'})}")
    start, start_zone = _read_value(tail, parameters.get("ZONE"))

    head, _, tail = lines[2].partition(":")
    if head.strip().upper() != "REPEAT":
        raise RuleTextError("the third line must be REPEAT:<DAILY|WEEKLY>;...")
    period, repeat = _split_parameters(tail)
    period = period.upper()
    if period not in PERIODS:
        raise RuleTextError(f"{period!r} is not one of {list(PERIODS)}")
    if set(repeat) - {"EVERY", "TIMES", "ENDS"}:
        raise RuleTextError(f"REPEAT carries unknown parameters {sorted(set(repeat) - {'EVERY', 'TIMES', 'ENDS'})}")
    if "EVERY" not in repeat:
        raise RuleTextError("REPEAT must carry EVERY=<n>")
    if ("TIMES" in repeat) == ("ENDS" in repeat):
        raise RuleTextError("REPEAT must carry exactly one of TIMES and ENDS")

    def whole(field: str) -> int:
        try:
            number = int(repeat[field])
        except ValueError:
            raise RuleTextError(f"{field}={repeat[field]!r} is not a whole number") from None
        if number < 1:
            raise RuleTextError(f"{field} must be one or more")
        return number

    return RuleSpec(
        summary=summary,
        zone=start_zone or "UTC",
        wall_start=start,
        period=period,
        interval=whole("EVERY"),
        count=whole("TIMES") if "TIMES" in repeat else None,
        until=None if "TIMES" in repeat else _read_value(repeat["ENDS"], None)[0],
    )


def slice_window(window: Window, seconds: int) -> tuple[Window, ...]:
    """Cut a stretch into consecutive pieces, the way the dispatcher walks a night."""

    step = timedelta(seconds=int(seconds))
    if step <= timedelta(0):
        raise ScheduleError("a slice must be longer than nothing")
    pieces: list[Window] = []
    cursor = window.start
    while cursor < window.end:
        end = min(cursor + step, window.end)
        pieces.append(Window(start=cursor, end=end))
        cursor = end
    return tuple(pieces)


def describe_zones() -> list[dict[str, Any]]:
    """The zone table as the dashboard prints it."""
    return [
        {
            "name": zone.name,
            "base_offset": zone.base_offset,
            "offsets": list(zone.offsets),
            "changes_at": [[a.isoformat(), b.isoformat(), o] for a, b, o in zone.periods],
        }
        for zone in (ZONES[name] for name in sorted(ZONES))
    ]
