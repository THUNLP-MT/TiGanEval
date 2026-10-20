"""The month's gate-pass readout, and what the mail house should run next."""

from support import (
    booking_lines,
    charge_for,
    drum_terms,
    expected_signups,
    half_width,
    ledger,
    points,
    rate,
    receipts,
    register,
    signed_up,
    split,
)


def _lifts(register_rows, receipt_rows):
    """What a pass is worth to its own account, and what the tag is worth next door."""

    invited, neighbours, untouched = split(register_rows, receipt_rows)
    base = rate(untouched)
    return (
        points(rate(invited) - base),
        points(rate(neighbours) - base),
        invited,
        untouched,
    )


def analyze(context):
    register_rows = register(context)
    receipt_rows = receipts(context)
    ledger_rows = ledger(context)
    lift, _tag, invited, untouched = _lifts(register_rows, receipt_rows)
    spread = half_width(invited, untouched)
    lines = booking_lines(ledger_rows)
    return {
        "ticket_effect_points": lift,
        "effect_range_points": [lift - spread, lift + spread],
        "bookings": lines,
        "tickets_charged": sum(line["tickets_charged"] for line in lines),
        "accounts_reached": sum(line["accounts_reached"] for line in lines),
        "credits_charged": sum(line["credits_charged"] for line in lines),
    }


def _affordable(context, drum, credits_left):
    terms = drum_terms(context, drum)
    if terms is None:
        return 0
    cap = terms["monthly_ticket_cap"]
    room = int(terms["names_left"])
    if cap is not None:
        room = min(room, int(cap) - int(terms["tickets_this_month"]))
    per_hundred = int(terms["credits_per_hundred"])
    return max(0, min(room, (credits_left // per_hundred) * 100))


def next_collection(context):
    register_rows = register(context)
    receipt_rows = receipts(context)
    stamped = sum(1 for row in register_rows if signed_up(row))
    short = int(context["target"]["activations"]) - stamped
    if short <= 0:
        return "stop"

    lift, tag, _invited, _untouched = _lifts(register_rows, receipt_rows)
    lift, tag = lift / 100.0, max(0.0, tag / 100.0)
    send_on = min(str(context["as_of"]), str(context["mail_house"]["cut_off"]))
    credits_left = int(context["account"]["credits_left"])

    def yields(drum, tickets):
        return expected_signups(
            context, register_rows, receipt_rows, drum, tickets, lift, tag
        )

    best = None
    for terms in context["drums"]:
        drum = str(terms["drum_id"])
        ceiling = _affordable(context, drum, credits_left)
        if ceiling <= 0 or yields(drum, ceiling) < short:
            continue
        # Tickets are billed by the hundred and a part-used hundred costs the
        # whole of it, so the run to look for is the shortest whole hundred
        # that covers the shortfall.
        low, high = 0, -(-ceiling // 100)
        while high - low > 1:
            middle = (low + high) // 2
            if yields(drum, min(middle * 100, ceiling)) >= short:
                high = middle
            else:
                low = middle
        tickets = min(high * 100, ceiling)
        charge = charge_for(context, drum, tickets)
        if best is None or charge < best[0]:
            best = (charge, drum, tickets)
    if best is None:
        return "stop"
    return [{"drum": best[1], "tickets": best[2], "send_on": send_on}]
