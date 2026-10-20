"""The September gate-pass readout, as I have been building it. -- Iris

The pivot is invited against uninvited off the register and the ticket export,
with the register lined up against the nightly counter so the two agree on how
many sign-ups the month has. The difference between the two rows is what a pass
is worth. The plan puts what is left of the grant on the cheapest ticket the
mail house prints, which is an estate drum.
"""

import csv
from math import sqrt


def rows_of(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def counted_through(register, counter):
    """The last day the register agrees with the counter's published total."""

    if not counter:
        return None
    total = int(counter[-1]["signups_to_date"])
    stamps = sorted(row["activated_at"] for row in register if row["activated_at"])
    days = [row["day"] for row in counter]
    best = days[-1]
    for day in days:
        if sum(1 for stamp in stamps if stamp <= day) == total:
            best = day
    return best


def pivot(context):
    register = rows_of(context["files"]["register"])
    receipts = rows_of(context["files"]["receipts"])
    counter = rows_of(context["files"]["counter"])
    through = counted_through(register, counter)
    invited_ids = {row["account_id"] for row in receipts}
    invited = [row for row in register if row["account_id"] in invited_ids]
    uninvited = [row for row in register if row["account_id"] not in invited_ids]

    def share(rows):
        if not rows:
            return 0.0
        joined = sum(
            1 for row in rows if row["activated_at"] and row["activated_at"] <= through
        )
        return joined / len(rows)

    return share(invited), len(invited), share(uninvited), len(uninvited), counter


def analyze(context):
    invited_rate, invited_n, uninvited_rate, uninvited_n, _counter = pivot(context)
    lift = 100.0 * (invited_rate - uninvited_rate)
    spread = 100.0 * 1.96 * sqrt(
        invited_rate * (1.0 - invited_rate) / max(1, invited_n)
        + uninvited_rate * (1.0 - uninvited_rate) / max(1, uninvited_n)
    )
    return {
        "ticket_effect_points": lift,
        "effect_range_points": [lift - spread, lift + spread],
        "bookings": [],
        "tickets_charged": 0,
        "accounts_reached": 0,
        "credits_charged": 0,
    }


def next_collection(context):
    """The rest of the grant on the cheapest ticket the mail house prints."""

    invited_rate, _n, _u, _m, counter = pivot(context)
    stamped = int(counter[-1]["signups_to_date"]) if counter else 0
    short = int(context["target"]["activations"]) - stamped
    if short <= 0:
        return "stop"
    tickets = int(-(-short // max(invited_rate, 0.001)))
    estates = [
        drum for drum in context["drums"] if str(drum["drum_id"]).startswith("estate:")
    ]
    estates.sort(key=lambda drum: -int(drum["names_left"]))
    return [
        {
            "drum": estates[0]["drum_id"],
            "tickets": tickets,
            "send_on": context["as_of"],
        }
    ]
