'A second readout, written from `full_information.md` and from nothing else.'

from datetime import date
from math import sqrt


def _gap(first, last):
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def _off_active(context):
    log = {}
    for row in context.get("account_states", ()):
        log.setdefault(str(row["account_id"]), []).append(row)
    return log


def _tally(context):
    'Account-days watched and escalations, per segment and per side.'

    question = int(context["escalation_window_days"])
    grace = int(context["grace_window_days"])
    last_day = str(context["window"]["last_day"])
    log = _off_active(context)
    table = {}
    for flag in context["flags"]:
        raised = str(flag["flag_date"])
        if raised > last_day:
            continue
        state = "active"
        for stretch in log.get(str(flag["account_id"]), ()):
            opened = str(stretch["effective_from"])
            closed = str(stretch["effective_to"])
            if opened <= raised and (not closed or raised < closed):
                state = str(stretch["state"])
        if state != "active":
            continue
        seen = _gap(raised, str(flag["last_observed_date"]))
        if seen < 1:
            continue
        opened_on = str(flag["start_date"])
        side = "same day" if str(flag["start_queue"]) == "same_day" else "held"
        if side == "held" and not (
            opened_on and _gap(raised, opened_on) <= grace
        ):
            seen = min(seen, grace)
        stop = min(seen, question)
        if stop < 1:
            continue
        went_up = str(flag["escalation_date"])
        day = _gap(raised, went_up) if went_up else None
        key = (float(flag["error_rate_7d"]), str(flag["plan_tier"]), side)
        entry = table.setdefault(key, [0.0, 0.0])
        if day is None or day > stop:
            entry[0] += stop
        else:
            entry[0] += day
            entry[1] += 1.0
    return table


def _shares(context):
    counts = {}
    for row in context["book"]["accounts"]:
        counts[(float(row["error_rate_7d"]), str(row["plan_tier"]))] = int(row["accounts"])
    whole = sum(counts.values())
    return {key: value / whole for key, value in counts.items()} if whole else {}


def _risk_and_wobble(entry, question):
    "The twenty-eight day risk this side's watching gives, and its wobble."

    days, events = entry
    if days <= 0:
        return 0.0, 0.0
    daily = events / days
    alive = (1.0 - daily) ** question


    slope = question * (1.0 - daily) ** (question - 1)
    return 1.0 - alive, slope * slope * events / (days * days)


def analyze(context, receipts):
    question = int(context["escalation_window_days"])
    table = _tally(context)
    shares = _shares(context)
    cost = 0.0
    wobble = 0.0
    weight = 0.0
    for segment, share in sorted(shares.items()):
        held = table.get((segment[0], segment[1], "held"))
        same = table.get((segment[0], segment[1], "same day"))
        if not held or not same or held[0] <= 0 or same[0] <= 0:
            continue
        held_risk, held_wobble = _risk_and_wobble(held, question)
        same_risk, same_wobble = _risk_and_wobble(same, question)
        cost += share * (held_risk - same_risk)
        wobble += share * share * (held_wobble + same_wobble)
        weight += share
    if weight <= 0:
        points, spread = 0.0, 0.0
    else:
        points = cost / weight * 100.0
        spread = sqrt(wobble) / weight * 100.0
    return {
        "cost_points": points,
        "cost_range_points": [points - 1.96 * spread, points + 1.96 * spread],
        "account_days": sum(entry[0] for entry in table.values()),
        "weeks": [
            {
                "receipt_id": entry["receipt_id"],
                "slots_charged": entry["slots_charged"],
                "rows_returned": entry["rows_returned"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    sheet = context["capacity"]
    left = int(sheet["slots_granted"]) - sum(
        int(entry["slots_charged"]) for entry in receipts
    )
    if left < int(sheet["smallest_week_slots"]):
        return "stop"
    return {
        "segment": "error_rate_7d=0.5,plan_tier=standard",
        "hold_share": min(0.35, float(sheet["hold_cap"])),
        "slots": min(int(sheet["slots_per_week"]), left),
    }
