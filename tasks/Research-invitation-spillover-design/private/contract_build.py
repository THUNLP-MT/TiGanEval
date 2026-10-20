'A second readout notebook, written from `full_information.md` and nothing else.'

import csv
import json
from math import sqrt


CONTRACT_RULES = (
    (
        "comparison-column",
        "Measure it against the accounts at addresses no ticket reached this month",
    ),
    (
        "address-is-the-door",
        "`address_id` in the register is what says who shares one",
    ),
    (
        "signups-off-the-stamps",
        "Sign-ups are the register's own `activated_at` stamps and nothing else.",
    ),
    (
        "address-is-the-unit",
        "four accounts at one door are one reading and not four, and both sides of the comparison have to be counted that way",
    ),
    (
        "nineteen-in-twenty",
        "The range the committee reads under a figure is the one that holds nineteen times in twenty",
    ),
    (
        "no-finite-population-correction",
        "the register is the whole office rather than a sample of it, so there is nothing to add on top of what the addresses leave open",
    ),
    (
        "barrel-is-refilled",
        "a run of tickets always lands on fewer accounts than it prints",
    ),
    (
        "second-pass-buys-nothing",
        "A second pass to an account that already has one buys nothing at all",
    ),
    (
        "already-stamped-buys-nothing",
        "neither does a pass to an account already stamped on the register, so a run is worth only what it does to the accounts that have not joined yet",
    ),
    (
        "tagged-door-buys-the-difference",
        "A pass into an address whose door already carries a tag buys only the difference between what a pass is worth and what the tag was already worth there.",
    ),
    (
        "fresh-door-lifts-the-household",
        "A pass into an address no ticket has reached buys its own account and lifts everyone else living there",
    ),
    (
        "the-tag-is-worth-its-own-number",
        "price a run with each of the two at its own size rather than at the same one",
    ),
    (
        "waitlist-cannot-be-sized",
        "nothing in the register says which accounts are still on it, so there is no sizing a booking against it",
    ),
    (
        "inside-the-balance",
        "inside the balance",
    ),
    (
        "the-whole-balance-is-the-months-own",
        "The reserve the mail house holds back is against bookings the desk makes on its own account, and the month's remaining plan draws on the whole balance",
    ),
    (
        "priced-by-the-hundred",
        "priced at each drum's own credits per hundred rounded up to the hundred",
    ),
    (
        "estate-allowance",
        "at most 1,200 tickets off any one estate drum in the month",
    ),
    (
        "cut-off",
        "posted on or before the 27th",
    ),
    (
        "names-left",
        "never asking a barrel for more tickets than it has names left",
    ),
    (
        "plan-reaches-the-published-line",
        "For planning, a run reaches the target when what it is expected to add leaves the month no more than a tenth of its current shortfall below the target, and never more than two sign-ups below it.",
    ),
    (
        "cost-disciplined-plan",
        "Among the plans that reach that line, do not hand back one that spends grossly more of the grant than another valid plan needs",
    ),
    (
        "stop-when-there",
        "Where the register already stands at or above the target, book nothing more and say so as a stop rather than as an empty list.",
    ),
    (
        "every-booking-once",
        "Every booking the ledger carries appears in the readout once, with its receipt id, the tickets it printed, the accounts those tickets landed on and the credits it charged",
    ),
    (
        "refusal-counted",
        "the turned-back one included, at nought tickets and its setup",
    ),
    (
        "totals-are-the-ledgers",
        "The month's totals in the readout are the ledger's totals.",
    ),
)


def _table(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _ledger(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _evidence(context):
    'The register, the ticket export and the ledger, keyed the way this file     wants them.'

    register = _table(context["files"]["register"])
    tickets = _table(context["files"]["receipts"])
    ledger = _ledger(context["files"]["ledger"])
    posted = {row["account_id"] for row in tickets}

    door = {}
    for row in register:
        door.setdefault(row["address_id"], []).append(row)
    reached_doors = {
        row["address_id"] for row in register if row["account_id"] in posted
    }
    return register, tickets, ledger, posted, door, reached_doors


def _columns(register, posted, reached_doors):
    'The two columns the contract names: the accounts a pass went to, and the     accounts at addresses no pass reached.'

    passes, untouched = [], []
    for row in register:
        if row["account_id"] in posted:
            passes.append(row)

        elif row["address_id"] not in reached_doors:
            untouched.append(row)
    return passes, untouched


def _joined(row):

    return bool(row["activated_at"])


def _share(rows):
    return sum(1 for row in rows if _joined(row)) / len(rows) if rows else 0.0


def _door_variance(rows):
    "How far a column's share can sit, counting one address as one reading."

    if not rows:
        return 0.0
    share = _share(rows)

    doors = {}
    for row in rows:
        here = doors.setdefault(row["address_id"], [0, 0])
        here[0] += 1
        here[1] += 1 if _joined(row) else 0
    if len(doors) < 2:
        return share * (1.0 - share) / len(rows)
    people = sum(here[0] for here in doors.values())
    spread = sum((here[1] - share * here[0]) ** 2 for here in doors.values())

    return len(doors) / (len(doors) - 1) * spread / (people * people)


def analyze(context):
    register, _tickets, ledger, posted, _door, reached_doors = _evidence(context)
    passes, untouched = _columns(register, posted, reached_doors)
    worth = 100.0 * (_share(passes) - _share(untouched))

    reach = 1.96 * sqrt(_door_variance(passes) + _door_variance(untouched))


    lines = [
        {
            "receipt_id": entry["receipt_id"],
            "drum": entry["drum"],
            "tickets_charged": int(entry["tickets_printed"]),
            "accounts_reached": int(entry["accounts_reached"]),
            "credits_charged": int(entry["credits_charged"]),
        }
        for entry in ledger
    ]
    return {
        "ticket_effect_points": worth,
        "effect_range_points": [worth - 100.0 * reach, worth + 100.0 * reach],
        "bookings": lines,

        "tickets_charged": sum(line["tickets_charged"] for line in lines),
        "accounts_reached": sum(line["accounts_reached"] for line in lines),
        "credits_charged": sum(line["credits_charged"] for line in lines),
    }


def _names_left(context, register, tickets, drum):
    'The names a drum can still pull, by account, or None where the office     keeps the list somewhere the register does not reach.'

    if drum == "citywide":
        members = [row["account_id"] for row in register]
    elif drum.startswith("estate:"):
        estate = drum.split(":", 1)[1]
        members = [row["account_id"] for row in register if row["estate"] == estate]
    else:

        return None

    used = {row["account_id"] for row in tickets if row["drum_id"] == drum}
    return [name for name in members if name not in used]


def _yield_of(context, register, tickets, posted, door, reached_doors, drum, count):
    'What a run of `count` tickets on one drum adds to the register.'

    left = _names_left(context, register, tickets, drum)
    if not left:
        return 0.0
    left_set = set(left)
    rows = {row["account_id"]: row for row in register}
    passes, untouched = _columns(register, posted, reached_doors)
    neighbours = [
        row
        for row in register
        if row["account_id"] not in posted and row["address_id"] in reached_doors
    ]
    base = _share(untouched)
    worth = max(0.0, _share(passes) - base)

    tag = max(0.0, _share(neighbours) - base)

    chance = 1.0 - (1.0 - 1.0 / len(left)) ** count

    added = 0.0
    doors_in_play = {}
    for name in left:
        row = rows[name]
        doors_in_play[row["address_id"]] = doors_in_play.get(row["address_id"], 0) + 1

        if _joined(row):
            continue

        if name in posted:
            continue

        added += chance * (worth - (tag if row["address_id"] in reached_doors else 0.0))

    for address, here in doors_in_play.items():
        if address in reached_doors:
            continue
        others = [
            row
            for row in door[address]
            if not _joined(row) and row["account_id"] not in posted
        ]
        for row in others:
            other_names = here - (1 if row["account_id"] in left_set else 0)
            opens = 1.0 - (1.0 - chance) ** max(0, other_names)
            added += opens * (1.0 - chance) * tag
    return added


def next_collection(context):
    register, tickets, _ledger, posted, door, reached_doors = _evidence(context)
    stamped = sum(1 for row in register if _joined(row))

    shortfall = int(context["target"]["activations"]) - stamped

    if shortfall <= 0:
        return "stop"
    want = shortfall - max(0.10 * shortfall, 2.0)


    credits = int(context["account"]["credits_left"])

    post_on = min(str(context["as_of"]), str(context["mail_house"]["cut_off"]))
    cheapest = None
    for terms in context["drums"]:
        drum = str(terms["drum_id"])
        price = int(terms["credits_per_hundred"])
        room = int(terms["names_left"])

        if terms["monthly_ticket_cap"] is not None:
            room = min(room, int(terms["monthly_ticket_cap"]) - int(terms["tickets_this_month"]))

        room = min(room, (credits // price) * 100)
        if room <= 0:
            continue

        def enough(size):
            return _yield_of(
                context, register, tickets, posted, door, reached_doors, drum, size
            ) >= want

        if not enough(room):
            continue

        low, high = 0, -(-room // 100)
        while high - low > 1:
            middle = (low + high) // 2
            if enough(min(middle * 100, room)):
                high = middle
            else:
                low = middle
        count = min(high * 100, room)
        charge = -(-count // 100) * price

        if cheapest is None or charge < cheapest[0]:
            cheapest = (charge, drum, count)
    if cheapest is None:
        return "stop"
    return [{"drum": cheapest[1], "tickets": cheapest[2], "send_on": post_on}]
