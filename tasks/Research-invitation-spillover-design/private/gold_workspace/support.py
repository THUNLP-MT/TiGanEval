"""Reading a month's evidence: who holds a pass, which addresses carry a tag,
who signed up and when, and what a drum still has to give."""

import csv
from math import sqrt

from protocol import load_json_lines

COVER = 1.96


# -- the files ---------------------------------------------------------------


def rows_of(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def register(context):
    return rows_of(context["files"]["register"])


def receipts(context):
    return rows_of(context["files"]["receipts"])


def counter(context):
    return rows_of(context["files"]["counter"])


def ledger(context):
    return load_json_lines(context["files"]["ledger"])


# -- who the month touched ---------------------------------------------------


def ticket_holders(receipt_rows):
    """Every account a ticket was addressed to, and the drums that reached it."""

    held = {}
    for row in receipt_rows:
        held.setdefault(row["account_id"], set()).add(row["drum_id"])
    return held


def touched_addresses(register_rows, holders):
    """The addresses a pass reached, whatever the drum."""

    address_of = {row["account_id"]: row["address_id"] for row in register_rows}
    return {address_of[account] for account in holders if account in address_of}


def split(register_rows, receipt_rows):
    """The month's three columns: passes, lifted neighbours, addresses untouched."""

    holders = ticket_holders(receipt_rows)
    touched = touched_addresses(register_rows, holders)
    invited, neighbours, untouched = [], [], []
    for row in register_rows:
        if row["account_id"] in holders:
            invited.append(row)
        elif row["address_id"] in touched:
            neighbours.append(row)
        else:
            untouched.append(row)
    return invited, neighbours, untouched


def signed_up(row, through=None):
    stamp = row["activated_at"]
    if not stamp:
        return False
    return through is None or stamp <= through


def rate(rows, through=None):
    if not rows:
        return 0.0
    return sum(1 for row in rows if signed_up(row, through)) / len(rows)


def points(value):
    return 100.0 * value


# -- how far the number can sit from what a pass is worth --------------------


def address_variance(rows):
    """The variance of a column's rate with the address as the unit.

    Everyone at one address decides largely together, so four accounts there
    are one reading and not four.
    """

    if not rows:
        return 0.0
    share = rate(rows)
    blocks = {}
    for row in rows:
        block = blocks.setdefault(row["address_id"], [0, 0])
        block[0] += 1
        block[1] += 1 if signed_up(row) else 0
    count = len(blocks)
    total = sum(block[0] for block in blocks.values())
    if count < 2 or total == 0:
        return share * (1.0 - share) / max(1, len(rows))
    spread = sum((block[1] - share * block[0]) ** 2 for block in blocks.values())
    return (count / (count - 1)) * spread / (total * total)


def half_width(invited, untouched):
    return points(COVER * sqrt(address_variance(invited) + address_variance(untouched)))


# -- the month's bill --------------------------------------------------------


def booking_lines(ledger_rows):
    return [
        {
            "receipt_id": entry["receipt_id"],
            "drum": entry["drum"],
            "tickets_charged": int(entry["tickets_printed"]),
            "accounts_reached": int(entry["accounts_reached"]),
            "credits_charged": int(entry["credits_charged"]),
        }
        for entry in ledger_rows
    ]


# -- what a drum still has to give -------------------------------------------


def pool_of(context, register_rows, drum):
    """The accounts a drum can still pull a name for, by name."""

    if drum == "citywide":
        members = [row["account_id"] for row in register_rows]
    elif drum.startswith("estate:"):
        estate = drum.split(":", 1)[1]
        members = [row["account_id"] for row in register_rows if row["estate"] == estate]
    else:
        members = None
    return members


def served_by(receipt_rows, drum):
    return {row["account_id"] for row in receipt_rows if row["drum_id"] == drum}


def drum_terms(context, drum):
    for row in context["drums"]:
        if row["drum_id"] == drum:
            return row
    return None


def charge_for(context, drum, tickets):
    terms = drum_terms(context, drum)
    hundreds = -(-int(tickets) // 100)
    return hundreds * int(terms["credits_per_hundred"])


def reach(names_left, tickets):
    """How many distinct accounts a run of tickets lands on.

    The drum returns a name to the barrel before the next pull, so a run of
    tickets longer than a handful lands on fewer accounts than it prints.
    """

    if names_left <= 0 or tickets <= 0:
        return 0.0
    return names_left * (1.0 - (1.0 - 1.0 / names_left) ** tickets)


def expected_signups(context, register_rows, receipt_rows, drum, tickets, lift, tag_lift):
    """What a run of tickets on one drum adds to the register by the target day."""

    members = pool_of(context, register_rows, drum)
    holders = ticket_holders(receipt_rows)
    touched = touched_addresses(register_rows, holders)
    by_account = {row["account_id"]: row for row in register_rows}
    at_address = {}
    for row in register_rows:
        at_address.setdefault(row["address_id"], []).append(row)
    if members is None:
        # The waitlist is a list of names the office keeps; which accounts are
        # still on it is not in these files, so nothing can be sized against it.
        return 0.0
    served = served_by(receipt_rows, drum)
    remaining = [by_account[name] for name in members if name not in served]
    if not remaining:
        return 0.0
    remaining_ids = {row["account_id"] for row in remaining}
    names_left = len(remaining)
    share = reach(names_left, tickets) / names_left

    total = 0.0
    per_address = {}
    for row in remaining:
        per_address[row["address_id"]] = per_address.get(row["address_id"], 0) + 1
        if signed_up(row) or row["account_id"] in holders:
            continue
        if row["address_id"] in touched:
            total += share * max(0.0, lift - tag_lift)
        else:
            total += share * lift
    for address, count in per_address.items():
        if address in touched:
            continue
        others = [
            row for row in at_address[address]
            if not signed_up(row) and row["account_id"] not in holders
        ]
        for row in others:
            other_names = count - (1 if row["account_id"] in remaining_ids else 0)
            opens = 1.0 - (1.0 - share) ** max(0, other_names)
            total += opens * (1.0 - share) * tag_lift
    return total
