"""Helpers for the service-start readout."""

from datetime import date, timedelta

QUEUES = ("same_day", "grace")


def days_between(first, last):
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def state_on(context):
    """The state each account was in on the day its flag was raised.

    The state log carries every stretch an account spent off `active`. An
    account with no stretch covering its flag date was the desk's to start.
    """

    periods = {}
    for row in context.get("account_states", ()):
        periods.setdefault(str(row["account_id"]), []).append(row)
    out = {}
    for row in context["flags"]:
        day = str(row["flag_date"])
        found = "active"
        for period in periods.get(str(row["account_id"]), ()):
            start = str(period["effective_from"])
            end = str(period["effective_to"])
            if start <= day and (not end or day < end):
                found = str(period["state"])
                break
        out[str(row["flag_id"])] = found
    return out


def arm_days(context):
    """(segment, side) -> [account-days at risk, escalations].

    Every flag the window raised on an account the desk could have started that
    day is counted from the flag date, on the side the desk put it on. A held
    account counts whether or not it was ever started, and stops counting when
    the grace window closes without a start, because after that it is no longer
    a wait. Nobody is counted past the day the export can speak for.

    A week booked now is served on a week after the window closed, so its rows
    are watching for the review that follows and are not part of this window's
    number.
    """

    horizon = int(context["escalation_window_days"])
    window = int(context["grace_window_days"])
    last_day = str(context["window"]["last_day"])
    states = state_on(context)
    cells = {}
    for row in context["flags"]:
        if str(row["flag_date"]) > last_day:
            continue
        if states[str(row["flag_id"])] != "active":
            continue
        flag_day = str(row["flag_date"])
        watched = days_between(flag_day, str(row["last_observed_date"]))
        if watched < 1:
            continue
        started = str(row["start_date"])
        waited = days_between(flag_day, started) if started else None
        if str(row["start_queue"]) == "same_day":
            side, reach = "same_day", horizon
        else:
            side = "grace"
            reach = horizon if waited is not None and waited <= window else window
        limit = min(horizon, watched, reach)
        if limit < 1:
            continue
        escalation = str(row["escalation_date"])
        day = days_between(flag_day, escalation) if escalation else None
        key = ((float(row["error_rate_7d"]), str(row["plan_tier"])), side)
        cell = cells.setdefault(key, [0.0, 0.0])
        if day is None or day > limit:
            cell[0] += limit
        else:
            cell[0] += day
            cell[1] += 1.0
    return cells


def risk(cell, horizon):
    """The chance of an escalation over the whole question's days."""

    if cell[0] <= 0:
        return 0.0
    return 1.0 - (1.0 - cell[1] / cell[0]) ** horizon


def variance(cell, horizon):
    if cell[0] <= 0:
        return 0.0
    rate = cell[1] / cell[0]
    if rate <= 0.0 or rate >= 1.0:
        return 0.0
    slope = horizon * (1.0 - rate) ** (horizon - 1)
    return slope * slope * rate * (1.0 - rate) / cell[0]


def book_weights(context):
    """The share of the desk's own book each segment carries."""

    counts = {}
    for row in context["book"]["accounts"]:
        counts[(float(row["error_rate_7d"]), str(row["plan_tier"]))] = int(row["accounts"])
    total = sum(counts.values())
    return {key: value / total for key, value in counts.items()} if total else {}


def combine(cells, weights, horizon):
    """The cost of waiting in points, the range it carries and the days behind it."""

    difference = 0.0
    spread = 0.0
    mass = 0.0
    for segment, weight in sorted(weights.items()):
        held = cells.get((segment, "grace"))
        same = cells.get((segment, "same_day"))
        if not held or not same or held[0] <= 0 or same[0] <= 0:
            continue
        difference += weight * (risk(held, horizon) - risk(same, horizon))
        spread += weight * weight * (variance(held, horizon) + variance(same, horizon))
        mass += weight
    if not mass:
        return 0.0, 0.0, 0.0
    days = sum(cell[0] for cell in cells.values())
    return difference / mass * 100.0, spread ** 0.5 / mass * 100.0, days


def slots_left(context, receipts):
    granted = int(context["capacity"]["slots_granted"])
    return granted - sum(int(entry["slots_charged"]) for entry in receipts)


def recent_mix(context):
    """The share of a week's flags each segment carries, over the window's own weeks."""

    counts = {}
    last_day = str(context["window"]["last_day"])
    for row in context["flags"]:
        if str(row["flag_date"]) > last_day:
            continue
        key = (float(row["error_rate_7d"]), str(row["plan_tier"]))
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    return {key: value / total for key, value in counts.items()} if total else {}


def held_days_per_row(cells, context):
    """How many days a held account has been worth on this desk so far."""

    held = [cell for (segment, side), cell in cells.items() if side == "grace"]
    if not held:
        return float(context["grace_window_days"])
    return sum(cell[0] for cell in held) / max(1.0, sum(1 for _ in held)) / 1.0


def segments(context):
    """The selectors the desk's sheet will take, widest first."""

    bands = sorted({float(row["error_rate_7d"]) for row in context["book"]["accounts"]})
    tiers = sorted({str(row["plan_tier"]) for row in context["book"]["accounts"]})
    out = ["all"]
    out.extend(f"plan_tier={tier}" for tier in tiers)
    out.extend(f"error_rate_7d={band:g}" for band in bands)
    out.extend(
        f"error_rate_7d={band:g},plan_tier={tier}" for band in bands for tier in tiers
    )
    return out


def matches(selector, segment):
    band, tier = segment
    text = str(selector).strip()
    if not text or text == "all":
        return True
    for clause in text.split(","):
        field, _, value = clause.strip().partition("=")
        if field == "plan_tier" and tier != value:
            return False
        if field == "error_rate_7d" and abs(band - float(value)) > 1e-9:
            return False
    return True


def spread_after(cells, weights, context, selector, hold, slots, horizon):
    """The range the desk would carry after one more week, as this notebook reads it.

    A booked week comes back two days short of the whole question, and a held
    account stops counting when the window closes without a start, so the days a
    row is worth depend on which side it lands on.
    """

    mix = recent_mix(context)
    inside = {key: share for key, share in mix.items() if matches(selector, key)}
    total = sum(inside.values())
    if total <= 0:
        return None
    short = horizon - int(context["export"]["record_lag_days"])
    grown = {key: [cell[0], cell[1]] for key, cell in cells.items()}
    for segment, share in inside.items():
        rows = slots * share / total
        for side, days in (
            ("same_day", rows * (1.0 - hold) * short),
            ("grace", rows * hold * short * 0.7),
        ):
            cell = grown.setdefault((segment, side), [0.0, 0.0])
            here = cells.get((segment, side))
            rate = here[1] / here[0] if here and here[0] > 0 else 0.0
            cell[0] += days
            cell[1] += days * rate
    _difference, spread, _days = combine(grown, weights, horizon)
    return spread
