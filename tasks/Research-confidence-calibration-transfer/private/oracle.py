'What the world says, counted off the listings rather than read off a report.'

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping, Sequence

from . import desk, workload, world


TOLERANCE = 0.005


DECOY_SLACK = 0.0025


INVARIANCE_TOLERANCE = 0.0035


RANGE_ROUNDING_SLACK = 0.11


QUEUES_IN_THE_RUN = 5
COVER = 2.5758


def served_shares(queue: world.Queue) -> dict[str, float]:
    'The mixture the traffic report gives for the month just closed.'

    rows = queue.traffic()
    total = sum(int(row["served_month_just_closed"]) for row in rows) or 1
    return {
        str(row["channel"]): int(row["served_month_just_closed"]) / total for row in rows
    }


def channel_rate(queue: world.Queue, channel: str, cut: float | None = None) -> float | None:
    "What share of a channel's auto-cleared listings come back violating."

    rows = [
        index
        for index in range(queue.size())
        if queue.channel[index] == channel and queue.auto_cleared(index, cut)
    ]
    if not rows:
        return None
    return sum(1 for index in rows if queue.violating[index]) / len(rows)


def population_rate(queue: world.Queue, cut: float | None = None) -> float:
    'The escape rate at one cut over the stream the queue serves today.'

    shares = served_shares(queue)
    weight = 0.0
    total = 0.0
    for channel, share in shares.items():
        rate = channel_rate(queue, channel, cut)
        if rate is None:
            continue
        weight += share
        total += share * rate
    return total / weight if weight else 0.0


def truth(queue: world.Queue) -> float:
    return population_rate(queue, queue.cut)


def loosest_cut_under_the_bar(queue: world.Queue) -> float | None:
    'The loosest band on the sheet whose escape rate holds under the bar.'

    holding = [edge for edge in world.BAND_EDGES if population_rate(queue, edge) <= queue.bar]
    return max(holding) if holding else None


def adjudicated(
    queue: world.Queue,
    entries: Sequence[Mapping[str, Any]],
    channel: str,
    cut: float | None = None,
) -> tuple[int, int]:
    "Listings of one channel a cut clears that carry an outcome, and how many     of them came back violating: the log's written rows plus the batches."

    edge = queue.cut if cut is None else float(cut)
    total = 0
    violating = 0
    for index in range(queue.size()):
        if queue.channel[index] != channel or not queue.auto_cleared(index, edge):
            continue
        if not queue.resolved(index):
            continue
        total += 1
        violating += 1 if queue.violating[index] else 0
    for row in desk.returned_rows(entries):
        if str(row["channel"]) != channel or float(row["stated_confidence"]) >= edge:
            continue
        total += 1
        violating += 1 if str(row["review_outcome"]) == "violating" else 0
    return total, violating


def evidence(
    queue: world.Queue,
    entries: Sequence[Mapping[str, Any]],
    cut: float | None = None,
) -> dict[str, dict[str, float]]:
    'Per channel: its share of the stream served now, and what is written.'

    shares = served_shares(queue)
    found: dict[str, dict[str, float]] = {}
    for channel in world.CHANNELS:
        total, violating = adjudicated(queue, entries, channel, cut)
        found[channel] = {
            "share": shares.get(channel, 0.0),
            "listings": total,
            "rate": (violating / total) if total else None,
        }
    return found


def evidence_rate(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]], cut: float
) -> float | None:
    'What one band comes back at when the desk counts the rows it has.'

    weight = 0.0
    total = 0.0
    for row in evidence(queue, entries, cut).values():
        if row["rate"] is None or row["share"] <= 0.0:
            continue
        weight += row["share"]
        total += row["share"] * row["rate"]
    return (total / weight) if weight else None


def thinnest_channel(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]]
) -> tuple[str | None, int]:
    'The channel carrying a share of the stream with the fewest outcomes.'

    rows = [
        (int(row["listings"]), channel)
        for channel, row in evidence(queue, entries).items()
        if float(row["share"]) > 0.0
    ]
    if not rows:
        return None, 0
    listings, channel = min(rows)
    return channel, listings


def reference_estimate(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]]
) -> float | None:
    'The number the written outcomes give for the stream served now.'

    weight = 0.0
    total = 0.0
    for row in evidence(queue, entries).values():
        if row["rate"] is None or row["share"] <= 0.0:
            continue
        weight += row["share"]
        total += row["share"] * row["rate"]
    return (total / weight) if weight else None


def supported_half_width(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]]
) -> float:
    'Half the tightest honest range for the listings that carry an outcome.'

    variance = 0.0
    unread = 0.0
    for row in evidence(queue, entries).values():
        share = float(row["share"])
        if share <= 0.0:
            continue
        if row["rate"] is None or not row["listings"]:
            unread += share * 0.5
            continue
        rate = float(row["rate"])
        variance += share * share * rate * (1.0 - rate) / float(row["listings"])
    return COVER * sqrt(variance) + unread


def adjudicated_total(queue: world.Queue, entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(row["listings"]) for row in evidence(queue, entries).values())


def unwritten_counted_clean(queue: world.Queue) -> float:
    'Every auto-cleared listing counted, an empty outcome cell read as clean.'

    shares = served_shares(queue)
    total = 0.0
    weight = 0.0
    for channel, share in shares.items():
        rows = [
            index
            for index in range(queue.size())
            if queue.channel[index] == channel and queue.auto_cleared(index)
        ]
        if not rows:
            continue
        good = sum(1 for index in rows if queue.resolved(index) and queue.violating[index])
        weight += share
        total += share * good / len(rows)
    return total / weight if weight else 0.0


def weighted_by_logged_rows(queue: world.Queue) -> tuple[float, float]:
    "Two readings that carry the log's own mix rather than the stream's."

    rows = [
        index
        for index in range(queue.size())
        if queue.auto_cleared(index) and queue.resolved(index)
    ]
    pooled = (
        sum(1 for index in rows if queue.violating[index]) / len(rows) if rows else 0.0
    )
    counts = {channel: 0 for channel in world.CHANNELS}
    for index in range(queue.size()):
        counts[queue.channel[index]] += 1
    total_rows = sum(counts.values()) or 1
    weight = 0.0
    total = 0.0
    for channel in world.CHANNELS:
        held = [
            index
            for index in range(queue.size())
            if queue.channel[index] == channel
            and queue.auto_cleared(index)
            and queue.resolved(index)
        ]
        if not held:
            continue
        share = counts[channel] / total_rows
        weight += share
        total += share * sum(1 for index in held if queue.violating[index]) / len(held)
    return pooled, (total / weight if weight else 0.0)


def chart_file_reading() -> float:
    'The number the file behind the chart gives, empty cells read as clean.'

    rows = [row for row in workload.sample_rows() if row["auto_cleared"] == "yes"]
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["review_outcome"] == "violating") / len(rows)


def cell_open_weight(
    queue: world.Queue,
    entries: Sequence[Mapping[str, Any]],
    channel: str,
    period: str,
) -> float:
    'How much of the stream served now one cell would close.'

    backlog = desk.cell_backlog(queue, entries, channel, period)
    cleared = [index for index in backlog if queue.auto_cleared(index)]
    if not cleared:
        return 0.0
    held = [
        index
        for index in range(queue.size())
        if queue.channel[index] == channel and queue.auto_cleared(index)
    ]
    if not held:
        return 0.0
    return served_shares(queue).get(channel, 0.0) * len(cleared) / len(held)


BATCH_FLOOR = 40


def affordable(queue: world.Queue, entries: Sequence[Mapping[str, Any]], channel: str) -> int:
    spec = queue.spec
    cap = int(spec["max_listings_per_batch"])
    unit = int(spec["credit_cost"][channel])
    return max(0, min(cap, desk.credits_left(queue, entries) // unit))


def cells(queue: world.Queue) -> list[tuple[str, str]]:
    return [
        (channel, period)
        for channel in world.CHANNELS
        for period in dict.fromkeys(queue.spec["periods"])
    ]


def open_cells(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]]
) -> list[tuple[float, tuple[str, str]]]:
    'Every cell the desk could fill with a batch worth making, best first.'

    found = []
    for channel, period in cells(queue):
        backlog = desk.cell_backlog(queue, entries, channel, period)
        if len(backlog) < BATCH_FLOOR or affordable(queue, entries, channel) < BATCH_FLOOR:
            continue
        weight = cell_open_weight(queue, entries, channel, period)
        if weight <= 0.0:
            continue
        found.append((weight, (channel, period)))
    return sorted(found, key=lambda item: (-item[0], item[1]))


def plan_is_allowed(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]], choice: Any
) -> str | None:
    'None when the batch is one this campaign can act on, else the incident.'

    available = open_cells(queue, entries)
    if choice == "stop":
        return None if not available else "batch_stops_with_work_left"
    if not isinstance(choice, Mapping):
        return "batch_is_not_a_request_or_a_stop"
    channel = choice.get("channel")
    period = choice.get("period")
    listings = choice.get("listings")
    if channel not in world.CHANNELS:
        return "batch_is_not_a_request_or_a_stop"
    if not isinstance(listings, int) or isinstance(listings, bool) or listings <= 0:
        return "batch_is_not_a_request_or_a_stop"
    if period is None or str(period) not in tuple(queue.spec["periods"]):
        return "batch_mixes_periods"
    if listings > int(queue.spec["max_listings_per_batch"]):
        return "batch_over_cap"
    backlog = desk.cell_backlog(queue, entries, channel, str(period))
    if not backlog:
        return "batch_cell_empty"
    cost = int(queue.spec["credit_cost"][channel]) * min(listings, len(backlog))
    if cost > desk.credits_left(queue, entries):
        return "batch_over_credits"
    if listings < BATCH_FLOOR:
        return "batch_uninformative"
    if not available:
        return "batch_uninformative"
    best = available[0][0]
    weight = cell_open_weight(queue, entries, channel, str(period))
    if abs(weight - best) > 1e-12:
        return "batch_uninformative"
    wanted = min(len(backlog), affordable(queue, entries, channel))
    if listings != wanted:
        return "batch_uninformative"
    return None


def one_allowed_plan(queue: world.Queue, entries: Sequence[Mapping[str, Any]]) -> Any:
    'A batch this campaign can act on now, or a stop when nothing is left.'

    available = open_cells(queue, entries)
    if not available:
        return "stop"
    channel, period = available[0][1]
    backlog = desk.cell_backlog(queue, entries, channel, period)
    return {
        "channel": channel,
        "period": period,
        "listings": min(len(backlog), affordable(queue, entries, channel)),
    }
