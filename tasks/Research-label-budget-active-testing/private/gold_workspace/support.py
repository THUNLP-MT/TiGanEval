"""Reading the review evidence: which labels hold, and what last month's tickets say."""

from fractions import Fraction
from itertools import combinations


def receipts(ledger):
    """One line per receipt the vendor issued, in the order it first issued it."""

    seen = {}
    for entry in ledger:
        seen.setdefault(entry["receipt_id"], entry)
    return list(seen.values())


def credits_spent(context, ledger):
    unique = receipts(ledger)
    sessions = {entry["session_id"] for entry in unique}
    return (
        sum(int(entry["price_credits"]) for entry in unique)
        + len(sessions) * int(context["setup_credits"])
    )


def _ticket_order(row):
    """The source order retained in a ticket id such as ``NG-I00042``."""

    identifier = str(row["ticket_id"])
    prefix = identifier.rstrip("0123456789")
    suffix = identifier[len(prefix):]
    return prefix, int(suffix) if suffix else -1, identifier


def recovered_segments(context):
    """{ticket id: segment}, including cells blanked inside preserved batches."""

    rows = sorted(context["intake"], key=_ticket_order)
    recovered = {}
    index = 0
    while index < len(rows):
        row = rows[index]
        if row["segment"]:
            recovered[row["ticket_id"]] = row["segment"]
            index += 1
            continue

        start = index
        while index < len(rows) and not rows[index]["segment"]:
            index += 1
        if index >= len(rows):
            continue
        tagged = rows[index]
        blank = rows[start:index]
        if all(
            row["channel"] == tagged["channel"]
            and row["product_line"] == tagged["product_line"]
            for row in blank
        ):
            for row in blank:
                recovered[row["ticket_id"]] = tagged["segment"]
    return recovered


def reading_stretch(context, ledger):
    """How far into a session the vendor's labels still match the settled sheet.

    The senior agents' sheet gives the queue for items the vendor also labelled.
    Every position up to the first place where the two part company is a
    position whose label the desk can stand behind.
    """

    settled = {row["item_id"]: row["settled_queue"] for row in context["adjudication"]}
    parted = [
        int(entry["position_in_session"])
        for entry in receipts(ledger)
        if entry["item_id"] in settled and entry["label"] != settled[entry["item_id"]]
    ]
    reached = [int(entry["position_in_session"]) for entry in receipts(ledger)]
    return min(parted) - 1 if parted else (max(reached) if reached else 0)


def segment_queue(context, ledger):
    """{segment: the queue its tickets belong in}, from the labels that hold."""

    stretch = reading_stretch(context, ledger)
    votes = {}
    for entry in receipts(ledger):
        if int(entry["position_in_session"]) > stretch:
            continue
        tally = votes.setdefault(entry["segment"], {})
        tally[entry["label"]] = tally.get(entry["label"], 0) + 1
    return {
        segment: max(sorted(tally), key=lambda queue: (tally[queue], queue))
        for segment, tally in votes.items()
    }


def intake_segments(context):
    recovered = recovered_segments(context)
    counts = {}
    for row in context["intake"]:
        segment = recovered.get(row["ticket_id"], row["segment"])
        if segment:
            counts[segment] = counts.get(segment, 0) + 1
    for line, members in context["catalogue"].items():
        for segment in members:
            counts.setdefault(segment, 0)
    return counts


def unread_segments(context, ledger):
    """Segments of last month's intake the desk still has no settled queue for."""

    mapping = segment_queue(context, ledger)
    counts = intake_segments(context)
    return sorted(
        (segment for segment, size in counts.items() if size and segment not in mapping),
        key=lambda segment: (-counts[segment], segment),
    )


def _line_queues(context, mapping, line):
    """The queues a ticket of this product line could belong in."""

    members = context["catalogue"].get(line, ())
    if any(segment not in mapping for segment in members):
        return None
    return {mapping[segment] for segment in members}


def tally(context, ledger):
    """Last month's tickets, split into what the desk can read and what it cannot."""

    mapping = segment_queue(context, ledger)
    recovered = recovered_segments(context)
    read = {"total": 0, "wrong": 0}
    by_channel = {}
    open_rows = []
    for row in context["intake"]:
        segment = recovered.get(row["ticket_id"], row["segment"])
        if segment and segment in mapping:
            wrong = int(row["predicted_queue"] != mapping[segment])
            read["total"] += 1
            read["wrong"] += wrong
            entry = by_channel.setdefault(row["channel"], {"total": 0, "wrong": 0})
            entry["total"] += 1
            entry["wrong"] += wrong
        else:
            open_rows.append({**row, "segment": segment})
    return mapping, read, by_channel, open_rows


def intake_rate(context, ledger):
    """The share of last month's tickets the classifier sent to the wrong queue.

    Blank segment cells are reattached to the source batches whose ids and
    boundaries survived the enrichment outage.  Channel carry-forward remains
    only as a conservative fallback while a recovered segment itself is unread.
    """

    _mapping, read, by_channel, open_rows = tally(context, ledger)
    if not read["total"]:
        return None
    overall = Fraction(read["wrong"], read["total"])
    wrong = Fraction(read["wrong"])
    for row in open_rows:
        seen = by_channel.get(row["channel"])
        wrong += Fraction(seen["wrong"], seen["total"]) if seen and seen["total"] else overall
    return wrong / len(context["intake"])


def intake_range(context, ledger):
    """Everything the recovered intake and the labels still leave open."""

    mapping, read, _by_channel, open_rows = tally(context, ledger)
    if not read["total"] and not open_rows:
        return None
    low = high = read["wrong"]
    for row in open_rows:
        if row["segment"]:
            low += 0
            high += 1
            continue
        queues = _line_queues(context, mapping, row["product_line"])
        if queues is None:
            low += 0
            high += 1
            continue
        low += 0 if row["predicted_queue"] in queues else 1
        high += 1 if queues - {row["predicted_queue"]} else 0
    total = len(context["intake"])
    return [Fraction(low, total), Fraction(high, total)]


def next_sessions(context, ledger):
    """One feasible way to maximize the unread intake brought into view."""

    stretch = reading_stretch(context, ledger)
    seat = min(stretch, int(context["session_item_cap"]))
    sittings = int(context["sessions_before_cutoff"])
    if seat <= 0 or sittings <= 0:
        return []
    bought = {entry["item_id"] for entry in ledger}
    cheapest = {}
    for row in context["pool"]:
        if row["item_id"] in bought:
            continue
        price = int(context["prices"][row["channel"]])
        held = cheapest.get(row["segment"])
        if held is None or price < held[0]:
            cheapest[row["segment"]] = (price, row["item_id"])
    budget = int(context["credits_contracted"]) - credits_spent(context, ledger)
    setup = int(context["setup_credits"])
    counts = intake_segments(context)
    candidates = sorted(segment for segment in unread_segments(context, ledger)
                        if segment in cheapest)
    limit = min(len(candidates), seat * sittings)
    best_mass = 0
    best_cost = 0
    best = ()
    for size in range(1, limit + 1):
        session_cost = setup * ((size + seat - 1) // seat)
        for chosen in combinations(candidates, size):
            cost = session_cost + sum(cheapest[segment][0] for segment in chosen)
            if cost > budget:
                continue
            mass = sum(counts.get(segment, 0) for segment in chosen)
            if (mass > best_mass
                    or (mass == best_mass and (not best or cost < best_cost))
                    or (mass == best_mass and cost == best_cost and chosen < best)):
                best_mass, best_cost, best = mass, cost, chosen
    ordered = sorted(best, key=lambda segment: (-counts.get(segment, 0), segment))
    picked = [cheapest[segment][1] for segment in ordered]
    return [
        {"items": picked[start:start + seat]} for start in range(0, len(picked), seat)
    ]
