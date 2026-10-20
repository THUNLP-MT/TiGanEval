"What the world says, computed from the world's own tickets and receipts."

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from typing import Any, Callable, Mapping, Sequence

from . import vendor
from .world import CHANNELS, Desk


TOLERANCE = Fraction(1, 100)

RANGE_SLACK = Fraction(15, 10000)

DRIFT_SLACK = Fraction(3, 1000)

NEAR_MISTAKE = Fraction(3, 1000)


def onset(desk: Desk) -> int:
    "Where this desk's reviewer stops reading. A world parameter, never read     by anything that judges a delivery: the sheet is what the desk can see."

    return int(desk.spec["ramp"]["onset"])


def settled_stretch(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> int:
    "How far into a sitting this desk's own evidence still stands behind a label."

    settled = {row["item_id"]: row["settled_queue"] for row in vendor.adjudication_rows(desk)}
    unique = vendor.distinct(entries)
    parted = [
        int(entry["position_in_session"]) for entry in unique
        if entry["item_id"] in settled and entry["label"] != settled[entry["item_id"]]
    ]
    if parted:
        return min(parted) - 1
    reached = [int(entry["position_in_session"]) for entry in unique]
    return max(reached) if reached else 0


def early_receipts(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The receipts written while the reviewer was still reading the ticket.'

    stretch = settled_stretch(desk, entries)
    return [
        entry for entry in vendor.distinct(entries)
        if int(entry["position_in_session"]) <= stretch
    ]


def segments_read(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> set[str]:
    'The segments the desk can put a queue against from what it has bought.'

    return {str(entry["segment"]) for entry in early_receipts(desk, entries)}


def intake_segments(desk: Desk) -> list[str]:
    return sorted({segment for _channel, segment in desk.spec["intake_mix"]})


def segments_open(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[str]:
    read = segments_read(desk, entries)
    return [segment for segment in intake_segments(desk) if segment not in read]


def intake_counts(desk: Desk) -> dict[str, int]:
    "How many of last month's tickets sit in each segment, tagged or not."

    counts: dict[str, int] = {}
    for (_channel, segment), blocks in desk.spec["intake_mix"].items():
        counts[segment] = counts.get(segment, 0) + int(blocks) * 64
    return counts


def truth(desk: Desk) -> Fraction:
    return desk.intake_truth()


def bounds(desk: Desk) -> tuple[Fraction, Fraction]:
    return desk.bounds()


def credits_statement(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> int:
    return vendor.credits_spent(desk, entries)


def _rate_over(desk: Desk, mapping: Mapping[str, str], rows: Sequence[Mapping[str, Any]]
               ) -> Fraction | None:
    counted = [row for row in rows if row.get("segment") in mapping]
    if not counted:
        return None
    wrong = sum(1 for row in counted if row["predicted_queue"] != mapping[row["segment"]])
    return Fraction(wrong, len(counted))


def settled_queues(desk: Desk) -> dict[str, str]:
    "The queue the senior agents' sheet puts against each item it reaches."

    return {str(row["item_id"]): str(row["settled_queue"])
            for row in vendor.adjudication_rows(desk)}


def sheet_partings(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> int:
    "How many items the sheet covers carry a queue the vendor's label did not."

    settled = settled_queues(desk)
    return sum(1 for entry in vendor.distinct(entries)
               if str(entry["item_id"]) in settled
               and str(entry["label"]) != settled[str(entry["item_id"])])


def _answers_a_receipt_can_give(desk: Desk) -> list[Callable[[Mapping[str, Any]], str]]:
    'The two ways a review reads what one receipt says about its item.'

    sheet = settled_queues(desk)

    def as_the_vendor_sent_it(row: Mapping[str, Any]) -> str:
        return str(row["label"])

    def with_the_sheet_in_front(row: Mapping[str, Any]) -> str:
        return sheet.get(str(row["item_id"]), str(row["label"]))

    return [as_the_vendor_sent_it, with_the_sheet_in_front] if sheet else [as_the_vendor_sent_it]


def face_value_map(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    'The queue each segment gets when every label on the ledger is believed.'

    votes: dict[str, dict[str, int]] = {}
    for entry in vendor.distinct(entries):
        tally = votes.setdefault(str(entry["segment"]), {})
        tally[str(entry["label"])] = tally.get(str(entry["label"]), 0) + 1
    return {
        segment: max(sorted(tally), key=lambda queue: (tally[queue], queue))
        for segment, tally in votes.items()
    }


def read_map(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    'The queue each segment gets from the labels written while reading.'

    return {segment: desk.correct_queue(segment) for segment in segments_read(desk, entries)}


def pool_reading(desk: Desk) -> Fraction:
    "The same share taken over the March export instead of last month's tickets."

    return desk.pool_rate()


def bought_readings(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'What the bought labels say about themselves, in the shapes a desk writes.'

    pool = desk.pool_index()
    unique = vendor.distinct(entries)
    shares = _intake_channel_shares(desk)
    values: list[Fraction] = []
    for answer in _answers_a_receipt_can_give(desk):
        for rows in (unique, list(entries)):
            if rows:
                wrong = sum(1 for row in rows
                            if answer(row) != pool[row["item_id"]]["predicted_queue"])
                values.append(Fraction(wrong, len(rows)))
        weighted = Fraction(0)
        covered = Fraction(0)
        for channel in CHANNELS:
            rows = [row for row in unique if row["channel"] == channel]
            if not rows:
                continue
            wrong = sum(1 for row in rows
                        if answer(row) != pool[row["item_id"]]["predicted_queue"])
            weighted += shares[channel] * Fraction(wrong, len(rows))
            covered += shares[channel]
        if covered:
            values.append(weighted / covered)
    return values


def _intake_channel_shares(desk: Desk) -> dict[str, Fraction]:
    counts = {channel: 0 for channel in CHANNELS}
    for (channel, _segment), blocks in desk.spec["intake_mix"].items():
        counts[channel] += int(blocks) * 64
    total = sum(counts.values())
    return {channel: Fraction(counts[channel], total) for channel in CHANNELS}


def draw_weighted_readings(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'What the bought labels say when each is weighted by the chance it was drawn.'

    pool = desk.pool_index()
    unique = vendor.distinct(entries)
    shares = _intake_channel_shares(desk)
    values: list[Fraction] = []

    for answer in _answers_a_receipt_can_give(desk):

        def weighted(rows: Sequence[Mapping[str, Any]],
                     answer: Any = answer) -> Fraction | None:
            total = Fraction(0)
            wrong = Fraction(0)
            for row in rows:
                chance = Fraction(str(row.get("draw_p") or 0))
                if chance <= 0:
                    continue
                weight = 1 / chance
                total += weight
                if answer(row) != pool[row["item_id"]]["predicted_queue"]:
                    wrong += weight
            return wrong / total if total else None

        plain = weighted(unique)
        if plain is not None:
            values.append(plain)
        carried = Fraction(0)
        covered = Fraction(0)
        for channel in CHANNELS:
            rows = [row for row in unique if row["channel"] == channel]
            share = weighted(rows)
            if share is None:
                continue
            carried += shares[channel] * share
            covered += shares[channel]
        if covered:
            values.append(carried / covered)
    return values


def face_value_reading(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> Fraction | None:
    "Last month's tickets counted against a map that believes every label."

    return _rate_over(desk, face_value_map(desk, entries), desk.intake_rows())


def read_only_readings(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[Fraction]:
    'Readings that leave out the segments the desk has never put a queue against.'

    mapping = read_map(desk, entries)
    rows = desk.intake_rows()
    resolved = [row for row in rows if row["segment"] in mapping]
    if not resolved:
        return []
    counted: dict[str, list[int]] = {}
    for row in resolved:
        entry = counted.setdefault(row["channel"], [0, 0])
        entry[0] += 1
        entry[1] += int(row["predicted_queue"] != mapping[row["segment"]])
    seen = sum(entry[0] for entry in counted.values())
    wrong = sum(entry[1] for entry in counted.values())
    plain = Fraction(wrong, seen)
    carried = Fraction(wrong)
    for row in rows:
        if row["segment"] in mapping:
            continue
        entry = counted.get(row["channel"])
        carried += Fraction(entry[1], entry[0]) if entry and entry[0] else plain
    return [plain, carried / len(rows)]


def sitting_cap(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> int:
    "The longest sitting whose every label the desk's own evidence stands behind."

    return min(settled_stretch(desk, entries), int(desk.spec["session_item_cap"]))


def unbought_pool(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    already = vendor.bought_items(entries)
    return [row for row in desk.pool_rows() if row["item_id"] not in already]


def buyable_segments(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    '{segment the desk cannot read yet: the cheapest label that would fix it}.'

    open_now = set(segments_open(desk, entries))
    cheapest: dict[str, int] = {}
    for row in unbought_pool(desk, entries):
        segment = str(row["segment"])
        if segment not in open_now:
            continue
        price = desk.price_of(row["channel"])
        if segment not in cheapest or price < cheapest[segment]:
            cheapest[segment] = price
    return cheapest


def reachable_mass(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> tuple[int, list[str]]:
    'The most intake a feasible next order can bring into view, and one such set.'

    counts = intake_counts(desk)
    cheapest = buyable_segments(desk, entries)
    budget = vendor.credits_left(desk, entries)
    setup = int(desk.spec["setup_credits"])
    stretch = sitting_cap(desk, entries)
    sessions = int(desk.spec["sessions_before_cutoff"])
    limit = min(len(cheapest), stretch * sessions)
    if stretch <= 0 or sessions <= 0 or limit <= 0:
        return 0, []

    best_mass = 0
    best_cost = 0
    best: tuple[str, ...] = ()
    segments = sorted(cheapest)
    for size in range(1, limit + 1):
        session_cost = setup * ((size + stretch - 1) // stretch)
        for chosen in combinations(segments, size):
            cost = session_cost + sum(cheapest[segment] for segment in chosen)
            if cost > budget:
                continue
            mass = sum(counts.get(segment, 0) for segment in chosen)
            if (mass > best_mass
                    or (mass == best_mass and (not best or cost < best_cost))
                    or (mass == best_mass and cost == best_cost and chosen < best)):
                best_mass, best_cost, best = mass, cost, chosen
    return best_mass, list(best)


def owner_block(desk: Desk, entries: Sequence[Mapping[str, Any]], size: int = 60
                ) -> list[dict[str, Any]]:
    'The block the owner would order: the items the model is least sure of.'

    rows = sorted(unbought_pool(desk, entries),
                  key=lambda row: (row["model_margin"], row["item_id"]))
    return rows[:size]
