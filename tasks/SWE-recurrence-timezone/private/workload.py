'Deterministic rule sets and the programs the schedule engine is driven through.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


BERLIN, SYDNEY, CHATHAM, KOLKATA, UTC = (
    "Europe/Berlin", "Australia/Sydney", "Pacific/Chatham", "Asia/Kolkata", "UTC"
)


_CUSTOMERS = ("acme", "northwind", "brightside", "kestrel", "lumen")


def _pick(seed: int, options: Sequence[Any]) -> Any:
    return options[int(seed) % len(options)]


def _rule(summary: str, zone: str, wall_start: str, *, period: str = "DAILY",
          interval: int = 1, count: int | None = None, until: str | None = None) -> dict[str, Any]:
    return {
        "summary": summary,
        "zone": zone,
        "wall_start": wall_start,
        "period": period,
        "interval": interval,
        "count": count,
        "until": until,
    }


def _win(start: str, end: str) -> dict[str, str]:
    return {"start": start, "end": end}


def _expand(label: str, check: str, rule: Mapping[str, Any], window: Mapping[str, str], **extra: Any) -> dict[str, Any]:
    return {"type": "expand", "label": label, "check": check, "rule": dict(rule), "window": dict(window), **extra}


def _export(label: str, rule: Mapping[str, Any]) -> dict[str, Any]:
    return {"type": "export", "label": label, "check": "export", "rule": dict(rule)}


def _merge(label: str, rules: Sequence[Mapping[str, Any]], window: Mapping[str, str]) -> dict[str, Any]:
    return {
        "type": "merge", "label": label, "check": "merge",
        "rules": [dict(rule) for rule in rules], "window": dict(window),
    }


def _paging(label: str, rule: Mapping[str, Any], window: Mapping[str, str], seconds: int) -> dict[str, Any]:
    return {
        "type": "paging", "label": label, "check": "paging",
        "rule": dict(rule), "window": dict(window), "slice_seconds": int(seconds),
    }


def _standup(seed: int, scale: int) -> list[dict[str, Any]]:
    'A daily standup and a weekly review over the fortnight both clocks move.'

    name = _pick(seed, _CUSTOMERS)
    return [
        _expand(
            "standup-week", "local",
            _rule(f"{name}-standup", BERLIN, "2026-03-26T09:00:00", count=8),
            _win("2026-03-26T00:00:00", "2026-04-03T00:00:00"),
        ),
        _expand(
            "review-fortnight", "local",
            _rule(f"{name}-review", SYDNEY, "2026-03-25T17:00:00", period="WEEKLY", count=4),
            _win("2026-03-25T00:00:00", "2026-04-16T00:00:00"),
        ),
    ]


def _transitions(seed: int, scale: int) -> list[dict[str, Any]]:
    'The two nights a year a wall-clock reading is not a plain reading.'

    name = _pick(seed, _CUSTOMERS)
    return [
        _expand(
            "export-switched-on", "transition",
            _rule(f"{name}-export", BERLIN, "2026-03-29T02:30:00", count=3),
            _win("2026-03-28T00:00:00", "2026-04-02T00:00:00"),
            wall_kind="gap", affected_wall="2026-03-29T02:30:00",
        ),
        _expand(
            "handover-october", "transition",
            _rule(f"{name}-handover", BERLIN, "2026-10-25T02:30:00", count=3),
            _win("2026-10-24T00:00:00", "2026-10-29T00:00:00"),
            wall_kind="ambiguous", affected_wall="2026-10-25T02:30:00",
        ),
    ]


def _export_program(seed: int, scale: int) -> list[dict[str, Any]]:
    'What the phone app reads back out of an exported series.'

    name = _pick(seed, _CUSTOMERS)
    return [
        _export("phone-export-open", _rule(f"{name}-standup", BERLIN, "2026-03-23T09:00:00", count=10)),
        _export(
            "phone-export-bounded",
            _rule(f"{name}-checkin", SYDNEY, "2026-05-04T17:00:00", until="2026-05-14T00:00:00"),
        ),
    ]


def _subscription(seed: int, scale: int) -> list[dict[str, Any]]:
    'A standing meeting held through two feeds, and a night of hourly pages.'

    name = _pick(seed, _CUSTOMERS)
    return [


        _expand(
            "standing-week", "local",
            _rule(f"{name}-sync", BERLIN, "2025-08-04T09:00:00", count=1000),
            _win("2026-10-19T00:00:00", "2026-10-24T00:00:00"),
        ),
        _merge(
            "two-feeds",
            [
                _rule(f"{name}-sync", BERLIN, "2026-10-19T09:00:00", count=5),
                _rule(f"{name}-sync", UTC, "2026-10-19T07:00:00", count=5),
            ],
            _win("2026-10-19T00:00:00", "2026-10-24T00:00:00"),
        ),
        _paging(
            "night-pages",
            _rule(f"{name}-night", BERLIN, "2026-10-23T02:30:00", count=5),
            _win("2026-10-24T20:00:00", "2026-10-25T20:00:00"), 3600,
        ),
    ]


def _release(seed: int, scale: int) -> list[dict[str, Any]]:
    one, two = _pick(seed, _CUSTOMERS), _pick(seed + 1, _CUSTOMERS)
    return [


        _expand(
            "berlin-standup", "local",
            _rule(f"{one}-standup", BERLIN, "2026-03-26T09:00:00", count=9),
            _win("2026-03-26T00:00:00", "2026-04-04T00:00:00"),
        ),
        _expand(
            "sydney-review", "local",
            _rule(f"{one}-review", SYDNEY, "2026-03-18T17:00:00", period="WEEKLY", count=5),
            _win("2026-03-18T00:00:00", "2026-04-16T00:00:00"),
        ),
        _expand(
            "chatham-briefing", "local",
            _rule(f"{two}-briefing", CHATHAM, "2026-09-24T08:15:00", count=7),
            _win("2026-09-24T00:00:00", "2026-10-01T00:00:00"),
        ),
        _expand(
            "kolkata-huddle", "local",
            _rule(f"{two}-huddle", KOLKATA, "2026-03-26T06:00:00", count=6),
            _win("2026-03-26T00:00:00", "2026-04-02T00:00:00"),
        ),


        _expand(
            "berlin-standing-standup", "local",
            _rule(f"{one}-standing", BERLIN, "2026-05-26T09:00:00", count=2000),
            _win("2026-06-01T00:00:00", "2026-06-08T00:00:00"),
            outlives_table=True,
        ),
        _expand(
            "sydney-standing-review", "local",
            _rule(f"{two}-standing", SYDNEY, "2027-01-11T17:00:00",
                  period="WEEKLY", until="2031-01-01T00:00:00"),
            _win("2027-02-01T00:00:00", "2027-03-01T00:00:00"),
            outlives_table=True,
        ),
        _expand(
            "chatham-standing-briefing", "local",
            _rule(f"{two}-standing-briefing", CHATHAM, "2027-09-20T08:15:00", count=1500),
            _win("2027-09-22T00:00:00", "2027-10-01T00:00:00"),
            outlives_table=True,
        ),


        _expand(
            "berlin-late-week", "local",
            _rule(f"{one}-planning", BERLIN, "2028-04-01T09:00:00", count=90),
            _win("2028-05-25T22:00:00", "2028-05-31T22:00:00"),
            stretch_at_table_edge=True,
        ),
        _expand(
            "sydney-late-week", "local",
            _rule(f"{two}-planning", SYDNEY, "2028-04-01T17:00:00", count=90),
            _win("2028-05-24T14:00:00", "2028-05-31T14:00:00"),
            stretch_at_table_edge=True,
        ),
        _expand(
            "kolkata-late-week", "local",
            _rule(f"{two}-late-huddle", KOLKATA, "2028-04-06T06:00:00", period="WEEKLY", count=20),
            _win("2028-05-24T18:30:00", "2028-05-31T18:30:00"),
            stretch_at_table_edge=True,
        ),


        _expand(
            "berlin-skipped", "transition",
            _rule(f"{one}-export", BERLIN, "2027-03-28T02:15:00", count=4),
            _win("2027-03-27T00:00:00", "2027-04-02T00:00:00"),
            wall_kind="gap", affected_wall="2027-03-28T02:15:00",
        ),
        _expand(
            "sydney-skipped", "transition",
            _rule(f"{two}-export", SYDNEY, "2026-10-04T02:30:00", count=3),
            _win("2026-10-03T00:00:00", "2026-10-08T00:00:00"),
            wall_kind="gap", affected_wall="2026-10-04T02:30:00",
        ),
        _expand(
            "berlin-repeated", "transition",
            _rule(f"{one}-handover", BERLIN, "2027-10-31T02:45:00", count=4),
            _win("2027-10-30T00:00:00", "2027-11-04T00:00:00"),
            wall_kind="ambiguous", affected_wall="2027-10-31T02:45:00",
        ),
        _expand(
            "chatham-repeated", "transition",
            _rule(f"{two}-handover", CHATHAM, "2026-04-05T03:15:00", count=3),
            _win("2026-04-04T00:00:00", "2026-04-09T00:00:00"),
            wall_kind="ambiguous", affected_wall="2026-04-05T03:15:00",
        ),


        _export("export-berlin-open", _rule(f"{one}-briefing", BERLIN, "2027-02-15T08:45:00", count=12)),
        _export("export-chatham-open", _rule(f"{two}-briefing", CHATHAM, "2026-09-24T08:15:00", count=7)),
        _export(
            "export-sydney-bounded",
            _rule(f"{one}-review", SYDNEY, "2026-03-18T17:00:00", period="WEEKLY", until="2026-06-24T07:00:00"),
        ),
        _export("export-utc-bounded", _rule(f"{two}-window", UTC, "2026-06-01T07:00:00", until="2026-06-20T07:00:00")),
        _export(
            "export-kolkata-bounded",
            _rule(f"{two}-huddle", KOLKATA, "2026-06-01T12:30:00", until="2026-06-20T07:00:00"),
        ),


        _merge(
            "three-feeds",
            [
                _rule(f"{one}-sync", BERLIN, "2026-06-01T09:00:00", count=7),
                _rule(f"{one}-sync", UTC, "2026-06-01T07:00:00", count=7),
                _rule(f"{one}-sync", KOLKATA, "2026-06-01T12:30:00", count=7),
            ],
            _win("2026-06-01T00:00:00", "2026-06-08T00:00:00"),
        ),
        _merge(
            "two-feeds",
            [
                _rule(f"{two}-review", SYDNEY, "2026-07-06T17:00:00", period="WEEKLY", count=3),
                _rule(f"{two}-review", UTC, "2026-07-06T07:00:00", period="WEEKLY", count=5),
            ],
            _win("2026-07-06T00:00:00", "2026-08-10T00:00:00"),
        ),


        _paging(
            "berlin-night-pages",
            _rule(f"{one}-night", BERLIN, "2027-10-29T02:30:00", count=5),
            _win("2027-10-30T20:00:00", "2027-10-31T20:00:00"), 3600,
        ),
        _paging(
            "sydney-night-pages",
            _rule(f"{two}-night", SYDNEY, "2026-10-02T02:30:00", count=5),
            _win("2026-10-03T00:00:00", "2026-10-05T00:00:00"), 3600,
        ),
        _paging(
            "kolkata-day-pages",
            _rule(f"{two}-day", KOLKATA, "2026-06-01T06:00:00", count=4),
            _win("2026-06-01T00:00:00", "2026-06-04T00:00:00"), 21600,
        ),
    ]


PROGRAM_BUILDERS = {
    "standup": _standup,
    "transitions": _transitions,
    "export": _export_program,
    "subscription": _subscription,
    "release": _release,
}


OPERATOR_NOTES: Mapping[str, tuple[str, ...]] = {
    "standup": (
        "Ticket 5120, Berlin customer: they sent a screenshot of the standup in their own calendar. It sits at 09:00 every working day of that week, on both sides of the 29th, and they say it has never moved.",
        "Ticket 5133, Sydney customer: the same complaint about their weekly review, which their own calendar shows at 17:00 every week including the one after the 5th.",
    ),
    "transitions": (
        "Sunday 29 March, 03:41 — the nightly export finished. The run log has one line for that night and it is stamped 03:30 Berlin time. Nothing was rerun.",
        "Sunday 25 October, 02:20 — the handover paged Ilse at 02:30 Berlin time, while the console was still showing the summer offset. She was the only person paged that hour, and the next page was the following night.",
    ),
    "export": (
        "Ticket 4471, support: the customer subscribed the exported file into the phone app. The standup came back into the phone as a series in the wrong place in the day.",
        "Same ticket, second file: their check-in stops on the 13th with us, and the phone has it running on to the 14th.",
    ),
    "subscription": (
        "Account note on this customer: they set that meeting up last August and booked it in for the next few years, and nobody has touched the rule since. Most of the standing meetings on the platform look like this one, and support only ever opens a week of any of them.",
        "Ticket 4902: the customer subscribes to the team feed and also holds their own invite for the same meeting. They are getting two reminders every morning for it, from the day they subscribed.",
        "Dispatch log, night of 25 October: the dispatcher asks for the next hour of reminders every hour. That night the 02:30 page went out against the 01:00 slot rather than the 00:00 one, and the operator on duty flagged the mismatch.",
    ),
}


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(str(profile))
    if builder is None:
        raise ValueError(f"unknown schedule program profile: {profile}")
    return [{**operation, "profile": str(profile)} for operation in builder(int(seed), int(scale))]


def operator_notes(profile: str) -> tuple[str, ...]:
    return tuple(OPERATOR_NOTES.get(str(profile), ()))


def zones_used(program: Sequence[Mapping[str, Any]]) -> list[str]:
    names: set[str] = set()
    for operation in program:
        rules = [operation["rule"]] if "rule" in operation else operation.get("rules", ())
        names.update(str(rule["zone"]) for rule in rules)
    return sorted(names)
