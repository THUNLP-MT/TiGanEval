"""Helpers for the one-tap reorder notebook."""

from datetime import date, timedelta
from math import erf, sqrt

ARMS = ("control", "treatment")


def finished_through(context):
    """The last enrolment day whose fourteen-day window has closed by `as_of`."""

    as_of = date.fromisoformat(context["as_of"])
    return (as_of - timedelta(days=int(context["reorder_window_days"]))).isoformat()


def lost_share(context):
    """Per day, the share of that day's reorder events the topic never took."""

    out = {}
    for row in context["ingestion"]:
        offered = int(row["accepted"]) + int(row["dropped"])
        if row["dropped"] and offered:
            out[str(row["day"])] = int(row["dropped"]) / offered
    return out


def cells(context, restore=True):
    """(arm, sessions_28d) -> [users measured, reorders they made]."""

    finished = finished_through(context)
    lost = lost_share(context)
    table = {}
    for row in context["enrolment"]:
        if row["day"] > finished:
            continue
        key = (row["arm"], int(row["sessions_28d"]))
        table.setdefault(key, [0, 0.0])[0] += int(row["users"])
    for row in context["reorders"]:
        if row["enrolled_on"] > finished:
            continue
        key = (row["arm"], int(row["sessions_28d"]))
        scale = 1.0 / (1.0 - lost.get(str(row["published_on"]), 0.0)) if restore else 1.0
        table.setdefault(key, [0, 0.0])[1] += int(row["reorders"]) * scale
    return table


def app_weights(context):
    """The share of the app the audience roll-up counted at each session count."""

    counts = {
        int(value): int(users)
        for value, users in context["base_audience"]["users_by_sessions_28d"].items()
    }
    total = sum(counts.values())
    return {value: counts[value] / total for value in counts}


def strata(table, weights):
    """The session counts both sides carry, with their weight and their rates."""

    out = []
    for value in sorted(weights):
        treated = table.get(("treatment", value))
        control = table.get(("control", value))
        if not treated or not control or not treated[0] or not control[0]:
            continue
        out.append(
            (
                weights[value],
                treated[1] / treated[0],
                treated[0],
                control[1] / control[0],
                control[0],
            )
        )
    return out


def difference(rows):
    return sum(weight * (rate_t - rate_c) for weight, rate_t, _nt, rate_c, _nc in rows)


def standard_error(rows):
    return sqrt(
        sum(
            weight**2
            * (rate_t * (1.0 - rate_t) / users_t + rate_c * (1.0 - rate_c) / users_c)
            for weight, rate_t, users_t, rate_c, users_c in rows
        )
    )


def _inverse_normal(target):
    """The point of the standard normal with `target` of the mass below it."""

    low, high = -12.0, 12.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if 0.5 * (1.0 + erf(middle / sqrt(2.0))) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def look_multiplier(context):
    """Multiplier for the charter's one-sided false-ship bound over all looks.

    The charter allows one chance in twenty across the whole watch, and the
    watch can be read at any of its looks, so the chance is divided among them.
    """

    looks = max(1, int(context["looks_granted"]))
    return _inverse_normal(1.0 - 0.05 / looks)


def share_by_day(context):
    """The treated share of each day's new enrolments, in percentage points."""

    totals = {}
    for row in context["enrolment"]:
        entry = totals.setdefault(row["day"], [0, 0])
        entry[0] += int(row["users"])
        if row["arm"] == "treatment":
            entry[1] += int(row["users"])
    return {day: 100.0 * treated / users for day, (users, treated) in totals.items() if users}


def carried_share(context):
    """The highest treated share the topic has already carried without shedding."""

    shares = share_by_day(context)
    clean = [
        shares[row["day"]]
        for row in context["ingestion"]
        if not int(row["dropped"]) and row["day"] in shares
    ]
    return int(max(clean)) if clean else 1


def points_left(context, ledger):
    granted = int(context["budget"]["share_day_points_granted"])
    return granted - sum(int(entry["share_day_points"]) for entry in ledger)
