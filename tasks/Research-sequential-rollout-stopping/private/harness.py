'Read one delivered watch notebook against the world it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload
from . import world as w


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-rollout-stopping-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

WATCH = workload.CURRENT.watch

BUCKETS: Mapping[str, str] = {
    "base_lift": "lift_failures",
    "collection_account": "ledger_failures",
    "lift_interval": "interval_failures",
    "stop_or_continue_plan": "plan_failures",
    "drop_ramp_invariance": "stability_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "base_lift": (
        "lift_closed_window_only",
        "lift_uncorrected_events",
        "lift_open_windows_counted",
        "base_lift_disagrees",
        "lift_wrong_at_recorded_look",
        "lift_population_wrong_on_another_watch",
        "lift_unrestored_on_another_watch",
        "lift_open_windows_on_another_watch",
        "lift_unreconciled_on_another_watch",
        "candidate_execution_failed",
    ),
    "collection_account": (
        "ledger_unreadable",
        "measurements_are_not_a_ledger",
        "receipt_missing",
        "booking_not_on_the_ledger",
        "receipt_double_counted",
        "ledger_wrong_on_another_watch",
        "candidate_execution_failed",
    ),
    "lift_interval": (
        "interval_absent",
        "interval_excludes_reported_lift",
        "interval_coverage_short",
        "interval_too_narrow",
        "interval_wider_than_the_evidence",
        "interval_wrong_at_recorded_look",
        "interval_short_for_more_looks",
        "interval_wrong_on_another_watch",
        "candidate_execution_failed",
    ),
    "stop_or_continue_plan": (
        "ships_early",
        "holds_after_the_line_is_cleared",
        "decision_boundary_strictness",
        "decision_is_not_a_watch_call",
        "exceeds_share_cap",
        "retriggers_shedding",
        "over_budget",
        "plan_is_not_a_booking_or_a_stop",
        "stopped_with_points_still_granted",
        "plan_uninformative",
        "call_wrong_on_another_watch",
        "booking_refused_on_another_watch",
        "stopped_on_another_watch",
        "booking_too_short_on_another_watch",
        "candidate_execution_failed",
    ),
    "drop_ramp_invariance": (
        "hardcoded_history",
        "moves_with_shed_fraction",
        "moves_with_ramp",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "lift_failures": (
        "lift_population_wrong_on_another_watch",
        "lift_unrestored_on_another_watch",
        "lift_open_windows_on_another_watch",
        "lift_unreconciled_on_another_watch",
    ),
    "ledger_failures": ("ledger_wrong_on_another_watch",),
    "interval_failures": ("interval_wrong_on_another_watch",),
    "plan_failures": (
        "call_wrong_on_another_watch",
        "booking_refused_on_another_watch",
        "stopped_on_another_watch",
        "booking_too_short_on_another_watch",
    ),
}


DECISION_KINDS: tuple[str, ...] = (
    "ships_early",
    "holds_after_the_line_is_cleared",
    "decision_is_not_a_watch_call",
)

_CARRY_OVER_KIND: Mapping[str, Mapping[str, str]] = {
    "lift_failures": {
        "lift_closed_window_only": "lift_population_wrong_on_another_watch",
        "lift_uncorrected_events": "lift_unrestored_on_another_watch",
        "lift_open_windows_counted": "lift_open_windows_on_another_watch",
        "base_lift_disagrees": "lift_unreconciled_on_another_watch",
    },
    "plan_failures": {
        **{kind: "call_wrong_on_another_watch" for kind in DECISION_KINDS},
        "exceeds_share_cap": "booking_refused_on_another_watch",
        "retriggers_shedding": "booking_refused_on_another_watch",
        "over_budget": "booking_refused_on_another_watch",
        "plan_is_not_a_booking_or_a_stop": "booking_refused_on_another_watch",
        "stopped_with_points_still_granted": "stopped_on_another_watch",
        "plan_uninformative": "booking_too_short_on_another_watch",
    },
}


_NAMING_ORDER: tuple[str, ...] = tuple(
    world.watch
    for world in (*workload.SIBLINGS, *workload.PARTNERS, workload.OUT_OF_REGIME)
)


def _naming_rank(watch: str) -> int:
    return _NAMING_ORDER.index(watch) if watch in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident the growth lead can open tables for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("watch") == WATCH else 1,
    )


def _carry_over_mode(bucket: str, modes: Sequence[str], kind: str) -> str:
    'Which carry-over incident a record of this kind belongs to.'

    mapped = _CARRY_OVER_KIND.get(bucket, {}).get(kind)
    return mapped if mapped in modes else modes[0]


def _returned_plan(record: Mapping[str, Any]) -> str:
    'The candidate output useful to the owner when a plan fails elsewhere.'

    if str(record.get("kind")) == "stopped_with_points_still_granted":
        return "stop"
    if "share_pct" in record or "days" in record:
        return f"{_show(record.get('share_pct'))} percent for {_show(record.get('days'))} days"
    return _show(record.get("reported"))


def _written_off_the_live_watch(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the watch the growth lead can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE or record.get("watch") == WATCH
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    mode = _carry_over_mode(bucket, modes, str(rows[0].get("kind")))
    same = [
        record
        for record in rows
        if _carry_over_mode(bucket, modes, str(record.get("kind"))) == mode
    ]
    named = min(
        (record for record in same if record.get("watch")),
        key=lambda record: _naming_rank(str(record["watch"])),
        default=same[0],
    )
    elsewhere = sorted({str(record["watch"]) for record in same if record.get("watch")})
    carried = {
        "watch": WATCH,
        "other_watch": str(named.get("watch")),
        "other_watches": len(elsewhere),
    }
    if "points_left" in named:
        carried["points_left"] = named["points_left"]
    if bucket == "lift_failures" and "reported_points" in named:
        carried["reported_points"] = named["reported_points"]
    if bucket == "plan_failures" and mode != "call_wrong_on_another_watch":
        carried["returned_plan"] = _returned_plan(named)
    return [_fail(mode, **carried)]


def _points(value: Any) -> str:
    return format(float(value), ".2f")


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{_points(value[0])} to {_points(value[1])}"
    return _show(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float, slack: float) -> bool:
    read = _number(value)
    return read is not None and abs(read - wanted) <= slack


def live_ledger(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The bookings this delivery has paid for, or why the ledger will not read.'

    try:
        return w.read_ledger(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def live_world(entries: Sequence[Mapping[str, Any]]) -> w.World:
    'The watch as it stands after everything the ledger says has been served.'

    extra = w.bookings_of(entries, len(workload.HISTORY_BOOKINGS))
    return w.booked(workload.CURRENT_SPEC, extra) if extra else workload.CURRENT


def history_ledger(world: w.World) -> list[dict[str, Any]]:
    "A watch's own ramp bookings, as its traffic service wrote them."

    return w.history_stream(world, history_bookings(world))


def history_bookings(world: w.World) -> list[dict[str, Any]]:
    "The booking requests that produced one watch's frozen ramp."

    shares = w.ramp_shares(world.spec)
    return [
        {"call_id": f"ramp-w{index + 1}", "share_pct": int(shares[index * 7]),
         "days": 7, "hold_ramp": True}
        for index in range(len(shares) // 7)
    ]


def aligned_partner(
    partner: w.World, entries: Sequence[Mapping[str, Any]]
) -> tuple[w.World, list[dict[str, Any]]]:
    "Advance a client split through the live watch's later bookings."

    later = [
        {
            "call_id": str(entry["call_id"]),
            "share_pct": int(entry["share_pct"]),
            "days": int(entry["days"]),
            "hold_ramp": bool(entry["hold_ramp"]),
        }
        for entry in list(entries)[len(workload.HISTORY_BOOKINGS) :]
    ]
    if not later:
        return partner, history_ledger(partner)
    grown = w.booked(partner.spec, later)
    return grown, w.history_stream(grown, [*history_bookings(partner), *later])


def _world_through(world: w.World, through: str) -> w.World:
    'The immutable world restricted to evidence published by one date.'

    spec = dict(world.spec)
    spec["looks"] = tuple(day for day in world.spec["looks"] if str(day) <= through)
    return w.World(
        spec=spec,
        days=tuple(day for day in world.days if str(day) <= through),
        enrolled={key: value for key, value in world.enrolled.items() if key[0] <= through},
        published={key: value for key, value in world.published.items() if key[3] <= through},
        shed={key: value for key, value in world.shed.items() if key[3] <= through},
        topic={day: value for day, value in world.topic.items() if day <= through},
    )


def historical_instances() -> list[dict[str, Any]]:
    'Readable scheduled weekly looks before the live window-close snapshot.'

    rows: list[dict[str, Any]] = []
    full_ledger = history_ledger(workload.CURRENT)
    for index, look in enumerate(workload.CURRENT.spec["looks"], start=1):
        through = str(look)
        if through >= workload.CURRENT.as_of:
            continue
        world = _world_through(workload.CURRENT, through)
        if not oracle.cells(world):
            continue
        rows.append(
            {
                "world": world,
                "ledger": [
                    dict(item)
                    for item in full_ledger
                    if str(item["served_from"]) <= through
                ],
                "record": f"weekly look {index} ({through})",
            }
        )
    return rows


def burn_state(
    base: w.World, bookings: Sequence[Mapping[str, Any]], entries: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    'The ledger after the points left have gone on single days at full share.'

    grown = [dict(entry) for entry in entries]
    made = [dict(item) for item in bookings]
    safe = oracle.safe_share(base)
    while base.points_left(grown) >= 1:
        share = min(safe, base.points_left(grown))
        one = {"share_pct": share, "days": 1, "hold_ramp": True}
        before = w.booked(base.spec, made)
        made.append(one)
        fresh = w.booked(base.spec, made).days[len(before.days) :]
        grown.append(
            w.receipt(
                base,
                f"burn-{len(grown) + 1:02d}",
                share,
                1,
                True,
                len(grown) + 1,
                grown[-1]["seal"] if grown else "",
                fresh[0],
                {"accepted": 0, "dropped": 0},
                {},
            )
        )
    return grown, made


def instances(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The watch under study, then the ones the same notebook is used on next.'

    extra = w.bookings_of(entries, len(workload.HISTORY_BOOKINGS))
    live = live_world(entries)
    burnt, burnt_bookings = burn_state(workload.CURRENT, extra, entries)
    rows: list[dict[str, Any]] = [
        {
            "label": live.watch,
            "world": live,
            "ledger": [dict(item) for item in entries],
            "plans": [
                {"base": workload.CURRENT, "bookings": extra, "world": live,
                 "ledger": [dict(item) for item in entries]},
                {"base": workload.CURRENT, "bookings": burnt_bookings,
                 "world": w.booked(workload.CURRENT_SPEC, burnt_bookings), "ledger": burnt},
            ],
        }
    ]
    for world in (*workload.SIBLINGS, workload.OUT_OF_REGIME):
        ledger = history_ledger(world)
        rows.append(
            {
                "label": world.watch,
                "world": world,
                "ledger": ledger,
                "plans": [{"base": world, "bookings": [], "world": world, "ledger": ledger}],
            }
        )
    for partner in workload.PARTNERS:
        world, ledger = aligned_partner(partner, entries)
        rows.append(
            {
                "label": world.watch,
                "world": world,
                "ledger": ledger,
                "plans": [
                    {
                        "base": partner,
                        "bookings": w.bookings_of(
                            ledger, len(history_bookings(partner))
                        ),
                        "world": world,
                        "ledger": ledger,
                    }
                ],
            }
        )
    return rows


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(0, _fail(CANDIDATE_FAILURE, error=error))


_MISREADINGS = (
    ("lift_closed_window_only", ("closed_window", "unrestored_closed_window")),
    ("lift_uncorrected_events", ("unrestored",)),
    ("lift_open_windows_counted",
     ("open_window", "open_window_pooled", "open_window_restored")),
)


def explanation(readings: Mapping[str, float], worlds: Mapping[str, w.World]) -> str | None:
    'The one misreading that accounts for this delivery on most of the watches.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = sum(
            1
            for watch, value in readings.items()
            if watch in worlds
            and any(
                _near(value, oracle.misreadings(worlds[watch])[family], oracle.CLASSIFY_SLACK)
                for family in families
            )
        )
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def _check_lift(
    review: Review, world: w.World, report: Mapping[str, Any], mode: str | None
) -> None:
    truth = oracle.truth(world)
    reported = report.get("lift_points")
    if _near(reported, truth, oracle.TOLERANCE):
        return
    shared = {
        "watch": world.watch,
        "reported_points": (
            _points(reported) if _number(reported) is not None else _show(reported)
        ),
    }
    families = dict(_MISREADINGS).get(mode or "", ())
    matches_mode = any(
        _near(reported, oracle.misreadings(world)[family], oracle.CLASSIFY_SLACK)
        for family in families
    )
    if _number(reported) is None or mode is None or not matches_mode:
        review.add("lift_failures", "base_lift_disagrees", **shared,
                   line_points=_points(world.spec["ship_line_points"]))
        return
    if mode == "lift_closed_window_only":
        review.add(
            "lift_failures",
            mode,
            **shared,
            measured_users=sum(
                users for (_arm, _value), (users, _made) in oracle.cells(world).items()
            ),
            audience_counted_on=str(world.spec["audience_counted_on"]),
        )
        return
    if mode == "lift_uncorrected_events":
        day, dropped = _worst_day(world)
        review.add("lift_failures", mode, **shared, day=day, dropped=dropped,
                   topic=str(world.spec["topic"]))
        return
    review.add("lift_failures", mode, **shared,
               window_days=int(world.spec["reorder_window_days"]),
               as_of=str(world.as_of))


def _worst_day(world: w.World) -> tuple[str, int]:
    rows = [row for row in world.ingestion_rows() if row["dropped"]]
    if not rows:
        return str(world.days[0]), 0
    worst = max(rows, key=lambda row: row["dropped"])
    return str(worst["day"]), int(worst["dropped"])


def _check_interval_width(review: Review, world: w.World, report: Mapping[str, Any]) -> bool:
    'The width the collected data supports. Returns whether the truth is held.'

    reported = report.get("lift_interval_points")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or reported[0] > reported[1]
    ):
        review.add("interval_failures", "interval_absent", watch=world.watch,
                   reported=_pair(reported))
        return False
    supported = oracle.half_width(world)
    width = (float(reported[1]) - float(reported[0])) / 2.0
    fields = {
        "watch": world.watch,
        "reported_interval": _pair(reported),
        "looks_granted": int(world.spec["looks_granted"]),
    }
    point = _number(report.get("lift_points"))
    if point is not None and not float(reported[0]) <= point <= float(reported[1]):
        review.add(
            "interval_failures",
            "interval_excludes_reported_lift",
            **fields,
            reported_points=_points(point),
        )
    if width < supported * oracle.NARROW_FACTOR:
        review.add("interval_failures", "interval_too_narrow", **fields)
    elif width > supported * oracle.WIDE_FACTOR:
        review.add("interval_failures", "interval_wider_than_the_evidence", **fields)
    truth = oracle.truth(world)
    return float(reported[0]) <= truth <= float(reported[1])


def _check_historical_readout(
    review: Review, world: w.World, record: str, report: Mapping[str, Any]
) -> None:
    'Check the number and range printed at a readable scheduled look.'

    reported = report.get("lift_points")
    if not _near(reported, oracle.reading(world), oracle.TOLERANCE):
        review.add(
            "lift_failures",
            "lift_wrong_at_recorded_look",
            watch=world.watch,
            record=record,
            as_of=world.as_of,
            reported_points=(
                _points(reported) if _number(reported) is not None else _show(reported)
            ),
        )

    interval = report.get("lift_interval_points")
    valid = (
        isinstance(interval, list)
        and len(interval) == 2
        and all(_number(item) is not None for item in interval)
        and float(interval[0]) <= float(interval[1])
    )
    supported = oracle.half_width(world)
    width = (
        (float(interval[1]) - float(interval[0])) / 2.0
        if valid else None
    )
    truth = oracle.truth(world)
    if (
        not valid
        or width is None
        or width < supported * oracle.NARROW_FACTOR
        or width > supported * oracle.WIDE_FACTOR
        or (
            _number(reported) is not None
            and not (float(interval[0]) <= float(reported) <= float(interval[1]))
        )
        or not (float(interval[0]) <= truth <= float(interval[1]))
    ):
        review.add(
            "interval_failures",
            "interval_wrong_at_recorded_look",
            watch=world.watch,
            record=record,
            as_of=world.as_of,
            reported_interval=_pair(interval),
            looks_granted=int(world.spec["looks_granted"]),
        )


def _interval_half_width(report: Mapping[str, Any]) -> float | None:
    'Half the width of one well-formed reported interval.'

    interval = report.get("lift_interval_points")
    if (
        not isinstance(interval, list)
        or len(interval) != 2
        or any(_number(item) is None for item in interval)
        or float(interval[0]) > float(interval[1])
    ):
        return None
    return (float(interval[1]) - float(interval[0])) / 2.0


def _check_look_budget(
    review: Review,
    baseline: w.World,
    baseline_report: Mapping[str, Any],
    longer: w.World,
    longer_report: Mapping[str, Any],
) -> bool:
    "Keep a longer sequential horizon from borrowing a shorter one's bound."

    baseline_width = _interval_half_width(baseline_report)
    longer_width = _interval_half_width(longer_report)
    if baseline_width is None:
        return True

    expected_growth = oracle.z_score(longer) / oracle.z_score(baseline)
    response_floor = baseline_width * (
        1.0 + oracle.LOOK_RESPONSE_FRACTION * (expected_growth - 1.0)
    )
    already_carries_longer_horizon = (
        longer_width is not None and longer_width >= oracle.half_width(longer)
    )
    responds_to_horizon = (
        longer_width is not None and longer_width >= response_floor
    )
    if responds_to_horizon or already_carries_longer_horizon:
        return True

    review.add(
        "interval_failures",
        "interval_short_for_more_looks",
        watch=baseline.watch,
        baseline_looks=int(baseline.spec["looks_granted"]),
        looks_granted=int(longer.spec["looks_granted"]),
        baseline_interval=_pair(baseline_report.get("lift_interval_points")),
        reported_interval=_pair(longer_report.get("lift_interval_points")),
    )
    return False


def _published_low_end(report: Mapping[str, Any]) -> float | None:
    'The low end of the bound this readout printed, when it printed one.'

    reported = report.get("lift_interval_points")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or float(reported[0]) > float(reported[1])
    ):
        return None
    return float(reported[0])


def _check_decision(review: Review, world: w.World, report: Mapping[str, Any]) -> None:
    'The call has to be the one the bound this readout printed supports.'

    low = _published_low_end(report)
    line = float(world.spec["ship_line_points"])
    wanted = oracle.decision(world) if low is None else (
        "ship" if low >= line else "continue"
    )
    reported = report.get("decision")
    if reported == wanted:
        return
    told = {
        "watch": world.watch,
        "as_of": world.as_of,
        "line_points": _points(world.spec["ship_line_points"]),
        "reported_interval": _pair(report.get("lift_interval_points")),
    }
    if reported not in ("ship", "continue"):
        review.add("plan_failures", "decision_is_not_a_watch_call", reported=_show(reported), **told)
    elif reported == "ship":
        review.add("plan_failures", "ships_early", **told)
    else:
        review.add("plan_failures", "holds_after_the_line_is_cleared", **told)


def _check_boundary_decision(
    review: Review, world: w.World, line: float, report: Mapping[str, Any]
) -> None:
    'Check the explicit equality rehearsal without narrating it as a live incident.'

    reported = report.get("decision")
    if reported == "ship":
        return
    told = {
        "watch": world.watch,
        "as_of": world.as_of,
        "line_points": _points(line),
        "reported_interval": _pair(report.get("lift_interval_points")),
    }
    if reported == "continue":
        review.add("plan_failures", "decision_boundary_strictness", **told)
    else:
        review.add(
            "plan_failures",
            "decision_is_not_a_watch_call",
            reported=_show(reported),
            **told,
        )


def _check_ledger(
    review: Review,
    world: w.World,
    report: Mapping[str, Any],
    ledger: Sequence[Mapping[str, Any]],
    error: str | None,
) -> None:
    where = {"watch": world.watch, "as_of": world.as_of}
    if error:
        review.add("ledger_failures", "ledger_unreadable", reason=str(error), **where)
        return
    rows = report.get("measurements")
    if not isinstance(rows, list):
        review.add("ledger_failures", "measurements_are_not_a_ledger",
                   reported=_show(rows), booked=len(ledger), **where)
        return
    billed = {str(item["call_id"]): item for item in ledger}
    seen: dict[str, int] = {}
    for row in rows:
        call_id = str(row.get("call_id"))
        seen[call_id] = seen.get(call_id, 0) + 1
        if seen[call_id] > 1:
            review.add("ledger_failures", "receipt_double_counted",
                       call_id=call_id, times_reported=seen[call_id], **where)
            return
        entry = billed.get(call_id)
        if entry is None or not all(
            _near(row.get(field), float(entry[field]), 0.0)
            for field in ("share_pct", "days", "share_day_points")
        ):
            review.add("ledger_failures", "booking_not_on_the_ledger",
                       call_id=call_id, booked=len(ledger), **where)
            return
    for call_id, entry in billed.items():
        if call_id not in seen:
            review.add("ledger_failures", "receipt_missing", call_id=call_id,
                       share_day_points=int(entry["share_day_points"]),
                       served_from=str(entry["served_from"]), booked=len(ledger), **where)
            return


def _check_plan(
    review: Review,
    base: w.World,
    bookings: Sequence[Mapping[str, Any]],
    ledger: Sequence[Mapping[str, Any]],
    answer: Any,
) -> None:
    world = base
    left = base.points_left(ledger)
    state = oracle.plan_state(base, bookings, left)
    shared = {
        "watch": world.watch,
        "points_left": left,
        "share_cap_pct": int(world.spec["share_cap_pct"]),
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                   reported=_show(answer))
        return
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not state["stop_only"]:
                review.add("plan_failures", "stopped_with_points_still_granted", **shared)
                return
            continue
        if not isinstance(choice, dict):
            review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                       reported=_show(choice))
            return
        share = _number(choice.get("share_pct"))
        days = _number(choice.get("days"))
        hold = bool(choice.get("hold_ramp", True))
        if (
            share is None or days is None
            or share != int(share) or days != int(days)
            or share < 1 or days < 1
        ):
            review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                       reported=_show(f"{_show(choice.get('share_pct'))} percent for "
                                      f"{_show(choice.get('days'))} days"))
            return
        share, days = int(share), int(days)
        named = {**shared, "share_pct": share, "days": days,
                 "share_day_points": oracle.booking_cost(world, share, days, hold)}
        if oracle.over_cap(world, share, days, hold):
            review.add("plan_failures", "exceeds_share_cap", **named,
                       cap_review_day=str(world.spec["cap_review_day"]))
            return
        if oracle.sheds_again(world, share, days, hold):
            review.add("plan_failures", "retriggers_shedding", **named,
                       ceiling_events=int(world.spec["ceiling_events"]))
            return
        if named["share_day_points"] > left:
            review.add("plan_failures", "over_budget", **named)
            return
        if state["stop_only"] or oracle.half_width_after(
            world, bookings, share, days, hold
        ) > state["bar"] * 1.005:
            review.add("plan_failures", "plan_uninformative", **named,
                       looks_granted=int(world.spec["looks_granted"]))
            return


def _check_stability(review: Review, readings: Mapping[str, float]) -> None:
    live = readings.get(WATCH)
    if live is None:
        return
    carried = workload.SIBLINGS[1].watch
    other = readings.get(carried)
    if (
        other is not None
        and abs(live - other) < 1e-6
        and abs(oracle.truth(workload.CURRENT) - oracle.truth(workload.SIBLINGS[1]))
        > oracle.CARRIED_OVER_GAP
    ):
        review.add("stability_failures", "hardcoded_history", watch=WATCH,
                   other_watch=carried, reported_points=_points(live))
        return
    for mode, partner in (
        ("moves_with_shed_fraction", workload.SHED_PARTNER),
        ("moves_with_ramp", workload.RAMP_PARTNER),
    ):
        value = readings.get(partner.watch)
        if value is None:
            continue
        if abs(live - value) > oracle.INVARIANCE_SLACK:
            review.add(
                "stability_failures",
                mode,
                watch=WATCH,
                other_watch=partner.watch,
                reported_points=_points(live),
                other_points=_points(value),
                moved_by=_points(abs(live - value)),
            )
            return


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (
            "it was still running after "
            f"{reported[len(_TIMEOUT_PHRASE):].strip()} and the console stopped it"
        )
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the watch notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every watch and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, ledger_error = live_ledger(Path(artifact_dir))
        rows = instances(entries)
        weekly_looks = historical_instances()
        contexts: list[dict[str, Any]] = []
        seen: dict[int, int] = {}

        def context_index(world: w.World) -> int:
            if id(world) not in seen:
                seen[id(world)] = len(contexts)
                contexts.append(world.context())
            return seen[id(world)]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        historical_reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[Mapping[str, Any], int]] = []
        for row in rows:
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": context_index(row["world"]),
                 "ledger": row["ledger"]}
            )
            for state in row["plans"]:
                plans.append((state, len(requests)))
                requests.append(
                    {"kind": "plan", "context": context_index(state["world"]),
                     "ledger": state["ledger"]}
                )
        for row in weekly_looks:
            historical_reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": context_index(row["world"]),
                 "ledger": row["ledger"]}
            )
        source = rows[0]["world"]
        look_budget_probes: list[tuple[w.World, int]] = []
        for looks_granted in workload.LOOK_BUDGET_PROBE_LOOKS:
            look_budget_world = w.World(
                spec={**source.spec, "looks_granted": looks_granted},
                days=source.days,
                enrolled=source.enrolled,
                published=source.published,
                shed=source.shed,
                topic=source.topic,
            )
            look_budget_index = len(requests)
            requests.append(
                {"kind": "report", "context": context_index(look_budget_world),
                 "ledger": rows[0]["ledger"]}
            )
            look_budget_probes.append((look_budget_world, look_budget_index))
        boundary_index = len(requests)
        requests.append(
            {"kind": "decision_boundary", "context": context_index(rows[0]["world"]),
             "ledger": rows[0]["ledger"]}
        )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {
                "watch": WATCH,
                "bookings_paid_for": len(entries),
                "weekly_looks_reviewed": len(weekly_looks),
                "look_budget_probe_looks": list(workload.LOOK_BUDGET_PROBE_LOOKS),
            }
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the watches"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        readings: dict[str, float] = {}
        worlds: dict[str, w.World] = {}
        for row, index in reports:
            value, _error = answer(index)
            reading = _number(dict(value or {}).get("lift_points")) if value else None
            if reading is not None:
                readings[row["world"].watch] = reading
                worlds[row["world"].watch] = row["world"]
        mode = explanation(readings, worlds)
        held: list[bool] = []
        stopped = False
        for row, index in reports:
            world = row["world"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("lift_failures", "interval_failures", "ledger_failures",
                     "stability_failures"),
                    error,
                )
                continue
            report = dict(value or {})
            _check_lift(review, world, report, mode)
            held.append(_check_interval_width(review, world, report))
            _check_decision(review, world, report)
            _check_ledger(
                review, world, report, row["ledger"],
                ledger_error if world.watch == WATCH else None,
            )
        for state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["plan_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            _check_plan(review, state["base"], state["bookings"], state["ledger"], value)
        baseline_value, baseline_error = answer(reports[0][1])
        for look_budget_world, look_budget_index in look_budget_probes:
            look_budget_value, look_budget_error = answer(look_budget_index)
            if look_budget_error is not None:
                stopped = True
                review.failures["interval_failures"].append(
                    _fail(CANDIDATE_FAILURE, error=look_budget_error)
                )
                break
            if baseline_error is None and not _check_look_budget(
                review,
                rows[0]["world"],
                dict(baseline_value or {}),
                look_budget_world,
                dict(look_budget_value or {}),
            ):
                break
        for row, index in historical_reports:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("lift_failures", "interval_failures", "ledger_failures",
                     "plan_failures"),
                    error,
                )
                continue
            report = dict(value or {})
            _check_historical_readout(
                review, row["world"], str(row["record"]), report
            )
            _check_ledger(review, row["world"], report, row["ledger"], None)
            _check_decision(review, row["world"], report)
        boundary, boundary_error = answer(boundary_index)
        if boundary_error is not None:
            stopped = True
            review.failures["plan_failures"].append(
                _fail(CANDIDATE_FAILURE, error=boundary_error)
            )
        elif isinstance(boundary, Mapping):
            line = _number(boundary.get("line_points"))
            report = boundary.get("report")
            if line is not None and isinstance(report, Mapping):
                source = rows[0]["world"]
                probe = w.World(
                    spec={**source.spec, "ship_line_points": line},
                    days=source.days,
                    enrolled=source.enrolled,
                    published=source.published,
                    shed=source.shed,
                    topic=source.topic,
                )
                _check_boundary_decision(review, probe, float(line), report)
        if held and sum(held) < oracle.COVERAGE * len(held):
            for row, index in reports:
                value, error = answer(index)
                if error is not None:
                    continue
                interval = dict(value or {}).get("lift_interval_points")
                truth = oracle.truth(row["world"])
                if (
                    isinstance(interval, list)
                    and len(interval) == 2
                    and all(_number(item) is not None for item in interval)
                    and not (float(interval[0]) <= truth <= float(interval[1]))
                ):
                    review.add(
                        "interval_failures",
                        "interval_coverage_short",
                        watch=row["world"].watch,
                        reported_interval=_pair(interval),
                        watches_reviewed=len(held),
                        watches_held=sum(held),
                    )
        _check_stability(review, readings)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_watch(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "watch": WATCH,
            "bookings_paid_for": len(entries),
            "watches_reviewed": len(rows),
            "weekly_looks_reviewed": len(weekly_looks),
            "look_budget_probe_looks": list(workload.LOOK_BUDGET_PROBE_LOOKS),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working-session record must contain a JSON object")
    return raw


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    "The watch's evidence as it stood on the day of one working session."

    through = str(record["as_of"])
    context = world.context()
    context["window"]["last_day"] = through
    context["as_of"] = through
    context["enrolment"] = [row for row in context["enrolment"] if row["day"] <= through]
    context["reorders"] = [
        row for row in context["reorders"] if row["published_on"] <= through
    ]
    context["ingestion"] = [row for row in context["ingestion"] if row["day"] <= through]
    context["looks"] = [day for day in context["looks"] if day <= through]
    return context


def _daily_view(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Enrolments and reorders by day, as the weekly job lays them out.'

    rows: dict[str, dict[str, Any]] = {}
    for row in context["enrolment"]:
        entry = rows.setdefault(row["day"], {"day": row["day"]})
        key = f"{row['arm']}_enrolled"
        entry[key] = entry.get(key, 0) + int(row["users"])
    for row in context["reorders"]:
        entry = rows.setdefault(row["published_on"], {"day": row["published_on"]})
        key = f"{row['arm']}_reorders_published"
        entry[key] = entry.get(key, 0) + int(row["reorders"])
    return [rows[day] for day in sorted(rows)]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    entries, error = live_ledger(root)
    world = live_world(entries) if not error else workload.CURRENT
    context = world.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("look", "date", "analyst", "as_of")},
        })
    return {
        "summary": (
            f"The {context['watch']} watch, the charter's terms and the working sessions on record."
        ),
        "measurements": {
            "watch": context["watch"],
            "window": context["window"],
            "as_of": context["as_of"],
            "reorder_window_days": context["reorder_window_days"],
            "ship_line_points": context["ship_line_points"],
            "share_cap_pct": context["share_cap_pct"],
            "cap_review_day": context["cap_review_day"],
            "topic": context["topic"],
            "assignment_topic": context["assignment_topic"],
            "budget": context["budget"],
            "share_day_points_spent": world.points_spent(entries),
            "share_day_points_left": world.points_left(entries),
            "looks_granted": context["looks_granted"],
            "looks_taken": context["looks"],
            "bookings_on_the_ledger": [
                {
                    "call_id": item["call_id"],
                    "share_pct": item["share_pct"],
                    "days": item["days"],
                    "hold_ramp": item["hold_ramp"],
                    "share_day_points": item["share_day_points"],
                    "served_from": item["served_from"],
                }
                for item in entries
            ],
            "ledger": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that recorded working session ran it.'

    record = _record(record_path)
    entries, _error = live_ledger(Path(artifact_dir))
    world = live_world(entries)
    context = snapshot(world, record)
    ledger = [
        item for item in history_ledger(workload.CURRENT)
        if str(item["served_from"]) <= str(record["as_of"])
    ]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "ledger": ledger},
            {"kind": "plan", "context": context, "ledger": ledger},
        ]},
    )
    look = {
        "look": record.get("look"),
        "date": record.get("date"),
        "analyst": record.get("analyst"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("as_of"),
        "bookings_on_the_ledger": [
            {"call_id": item["call_id"], "share_pct": item["share_pct"],
             "days": item["days"], "share_day_points": item["share_day_points"],
             "served_from": item["served_from"]}
            for item in ledger
        ],
        "by_day": _daily_view(context),
        "ingestion": [dict(row) for row in context["ingestion"]],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('look')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "watch": context["watch"]},
            "public": {"look": look, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('look')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "watch": context["watch"],
            "as_of": context["as_of"],
            "ship_line_points": context["ship_line_points"],
            "share_day_points_spent": sum(int(item["share_day_points"]) for item in ledger),
        },
        "public": {
            "look": look,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_booking(
    artifact_dir: Path, share_pct: Any, days: Any, hold_ramp: Any, call_id: Any
) -> Mapping[str, Any]:
    entries, error = live_ledger(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return w.collect(
        Path(artifact_dir), workload.CURRENT, workload.HISTORY_BOOKINGS,
        share_pct, days, hold_ramp, call_id,
    )


def starting_ledger() -> dict[str, Any]:
    'The ledger the watch starts from: the five weekly ramp bookings.'

    return {
        "watch": workload.CURRENT.watch,
        "entries": w.history_stream(workload.CURRENT, workload.HISTORY_BOOKINGS),
    }
