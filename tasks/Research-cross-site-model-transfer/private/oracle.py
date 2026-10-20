'What the world says, computed from the tickets rather than from a report.'

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping, Sequence

from . import workload, world


TOLERANCE = 0.02


DECOY_SLACK = 0.006

SHARE_SLACK = 0.012

COMBINATION_SLACK = 0.008


GROUP_SLACK = 0.005


RANGE_FLOOR = 0.90
RANGE_CEILING = 1.45


TAIL_FLOOR = 0.50

COVER = 1.96


Window = tuple[Any, Any]


def full_window() -> Window:
    return (None, None)


def unseen_window(stream: world.Stream) -> Window | None:
    "The prior-contact window this centre's queue never shows a reviewer."

    threshold = stream.threshold
    if threshold <= 0:
        return None
    window = (None, threshold - 1)


    return window if stream.indices(*window) else None


def queued_window(stream: world.Stream) -> Window:
    threshold = stream.threshold
    return (threshold if threshold > 0 else None, None)


def windows(stream: world.Stream) -> list[Window]:
    unseen = unseen_window(stream)
    if unseen is None:
        return [full_window()]
    return [unseen, queued_window(stream)]


def window_share(stream: world.Stream, window: Window) -> float:
    total = stream.size()
    if not total:
        return 0.0
    return len(stream.indices(*window)) / total


def window_error(stream: world.Stream, window: Window) -> float | None:
    rows = stream.indices(*window)
    if not rows:
        return None
    return sum(1 for index in rows if stream.wrong(index)) / len(rows)


def served_error(stream: world.Stream) -> float:
    return float(window_error(stream, full_window()) or 0.0)


def source_holdout_error() -> float:
    'The error the March fit read off the Ridgeline rows it held back.'

    pool = workload.ridgeline_pool()
    rows = workload.reserved_rows()
    return sum(1 for index in rows if pool.wrong(index)) / len(rows)


def ledger_rows(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for entry in entries for row in entry.get("observed", {}).get("rows", ())]


def rows_in_window(entries: Sequence[Mapping[str, Any]], window: Window) -> list[Mapping[str, Any]]:
    low, high = window
    kept = []
    for row in ledger_rows(entries):
        contacts = int(row["prior_contacts"])
        if low is not None and contacts < int(low):
            continue
        if high is not None and contacts > int(high):
            continue
        kept.append(row)
    return kept


def reviewed_error(entries: Sequence[Mapping[str, Any]], window: Window) -> float | None:
    rows = rows_in_window(entries, window)
    if not rows:
        return None
    wrong = sum(1 for row in rows if int(row["pipeline_decision"]) != int(row["reviewed_label"]))
    return wrong / len(rows)


def units_left(stream: world.Stream, entries: Sequence[Mapping[str, Any]]) -> int:
    return world.units_left(stream, entries)


def queue_only_error(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> float | None:
    'The number the reviewed tickets give when they stand for the stream.'

    return reviewed_error(entries, queued_window(stream))


def rows_weighted_error(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> float | None:
    'Each window weighted by the rows bought in it rather than by the counters.'

    total = 0
    weighted = 0.0
    for window in windows(stream):
        rows = rows_in_window(entries, window)
        rate = reviewed_error(entries, window)
        if rate is None:
            continue
        total += len(rows)
        weighted += rate * len(rows)
    if not total:
        return None
    return weighted / total


def supported_components(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> tuple[float, float, float]:
    'The observed contribution, sampling spread and wholly unread share.'

    point = 0.0
    variance = 0.0
    unmeasured = 0.0
    for window in windows(stream):
        share = window_share(stream, window)
        if share <= 0.0:
            continue
        rows = rows_in_window(entries, window)
        if not rows:
            unmeasured += share
            continue


        rate = reviewed_error(entries, window) or 0.0
        point += share * rate
        variance += share * share * rate * (1.0 - rate) / len(rows)
    return point, COVER * sqrt(variance), unmeasured


def supported_bounds(
    stream: world.Stream,
    entries: Sequence[Mapping[str, Any]],
    *,
    spread_scale: float = 1.0,
) -> tuple[float, float]:
    'Bounds implied by the reviewed rows and the counter-defined shares.'

    point, spread, unmeasured = supported_components(stream, entries)
    return (
        max(0.0, point - spread * float(spread_scale)),
        min(1.0, point + spread * float(spread_scale) + unmeasured),
    )


def supported_half_width(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> float:
    'Compatibility summary: half the unclipped supported interval width.'

    _point, spread, unmeasured = supported_components(stream, entries)
    return spread + unmeasured * 0.5


def request_cost(stream: world.Stream, channel: str, rows: int) -> int:
    return int(stream.context()["review"]["unit_cost"][channel]) * int(rows)


def affordable_rows(stream: world.Stream, entries: Sequence[Mapping[str, Any]], channel: str) -> int:
    context = stream.context()
    cap = int(context["review"]["max_rows_per_request"][channel])
    unit = int(context["review"]["unit_cost"][channel])
    return max(0, min(cap, units_left(stream, entries) // unit))


def plan_is_allowed(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]], choice: Any
) -> str | None:
    'None when the request is one this centre can act on, else the incident.'

    unseen = unseen_window(stream)
    export_rows = affordable_rows(stream, entries, "export")
    if choice == "stop":
        if unseen is not None and export_rows > 0:
            return "request_leaves_the_unreviewed_tickets_thin"
        return None
    if not isinstance(choice, Mapping):
        return "request_is_not_a_review_or_a_stop"
    site = choice.get("site")
    channel = choice.get("channel")
    rows = choice.get("rows")
    low, high = choice.get("prior_contacts_min"), choice.get("prior_contacts_max")
    if channel not in world.CHANNELS or not isinstance(rows, int) or isinstance(rows, bool):
        return "request_is_not_a_review_or_a_stop"
    if rows <= 0:
        return "request_is_not_a_review_or_a_stop"
    for value in (low, high):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            return "request_is_not_a_review_or_a_stop"
    if low is not None and high is not None and int(low) > int(high):
        return "request_is_not_a_review_or_a_stop"
    if site is None:
        return "request_is_not_a_review_or_a_stop"
    remaining = units_left(stream, entries)
    if remaining <= 0:
        return "request_after_quarter_units_spent"
    if str(site) != stream.site:
        return "request_buys_source_centre_labels"
    cap = int(stream.context()["review"]["max_rows_per_request"][str(channel)])
    if rows > cap:
        return "request_over_the_per_request_cap"
    if request_cost(stream, str(channel), rows) > remaining:
        return "request_over_the_quarter_units"
    if unseen is None:
        return "request_buys_reviews_with_nothing_hidden"
    expected_low, expected_high = unseen
    same_low = low == expected_low or (expected_low is None and low == 0)
    reaches_whole_unseen = same_low and high == expected_high
    if reaches_whole_unseen and channel == "queue":
        return "request_uses_the_queue_for_tickets_it_never_shows"
    if channel != "export" or not reaches_whole_unseen:
        return "request_does_not_reach_the_whole_unreviewed_band"
    return None


def one_allowed_plan(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> Any:
    'A request this centre can act on now, or a stop when nothing is left.'

    unseen = unseen_window(stream)
    export_rows = affordable_rows(stream, entries, "export")
    if unseen is not None and export_rows > 0:
        return {
            "site": stream.site,
            "channel": "export",
            "prior_contacts_min": None,
            "prior_contacts_max": int(unseen[1]),
            "rows": export_rows,
        }
    return "stop"
