"""Reading the readout evidence: who is comparable, and what the queue lost."""

from fractions import Fraction

ARMS = ("control", "treatment")


def indexed(context):
    """The session table as {(day, arm, visit): row}, and the window's days."""

    table = {(row["day"], row["arm"], row["visit"]): row for row in context["sessions_by_day"]}
    days = sorted({row["day"] for row in context["sessions_by_day"]})
    return table, days


def rules_off(context):
    """The day-slices whose rows were written before the rule set reached them."""

    return {
        (row["day"], row["arm"])
        for row in context["sessions_by_day"]
        if row["crawler_rules"] == "off"
    }


def shed_by_slice(context):
    """{(day, arm): confirmations the queue shed on that arm's topic that day}."""

    arm_of = {context["serving"][arm]["topic"]: arm for arm in ARMS}
    lost = {}
    for row in context["checkout_queue"]:
        arm = arm_of.get(row["topic"])
        if arm is not None and row["dropped"]:
            lost[(row["day"], arm)] = lost.get((row["day"], arm), 0) + int(row["dropped"])
    return lost


def crawlers_found(context, receipts):
    """Rescan counts that still sit inside the table, slice by slice.

    A rescan of a slice the rule set had already cleaned reports sessions the
    table never carried, so it is a receipt to account for and not a count to
    take off anything.
    """

    open_rows = rules_off(context)
    found = {}
    for entry in receipts:
        key = (entry["day"], entry["arm"])
        if key in open_rows:
            found[key] = int(entry["observed"]["crawler_sessions"])
    return found


def cohort(context, receipts):
    """Per arm: the people who arrived first inside the window, and their buys.

    Sessions are the first-visit rows with the crawler sessions the rescans
    found taken out. Confirmations are what the table holds plus the share of
    that day's shed confirmations the first-visit rows would have carried, the
    shedder taking the head of the buffer without reading the payload.
    """

    table, days = indexed(context)
    lost = shed_by_slice(context)
    found = crawlers_found(context, receipts)
    result = {}
    for arm in ARMS:
        sessions = 0
        held = 0
        restored = Fraction(0)
        shed = 0
        for day in days:
            first = table[(day, arm, "first")]
            later = table[(day, arm, "returning")]
            sessions += int(first["sessions"]) - found.get((day, arm), 0)
            held += int(first["confirmations"])
            missing = lost.get((day, arm), 0)
            shed += missing
            total = int(first["confirmations"]) + int(later["confirmations"])
            if missing and total:
                restored += Fraction(missing * int(first["confirmations"]), total)
        result[arm] = {
            "sessions": sessions,
            "confirmations": held + restored,
            "in_the_table": held,
            "shed": shed,
        }
    return result


def rate(counts, extra=0):
    return Fraction(counts["in_the_table"] + extra, counts["sessions"])


def bounds(cohorts):
    """The lift over every way the shed confirmations could have fallen."""

    control, treatment = cohorts["control"], cohorts["treatment"]
    low = rate(treatment) - rate(control, control["shed"])
    high = rate(treatment, treatment["shed"]) - rate(control)
    return [low, high]


def units_left(context, receipts):
    granted = int(context["archive"]["units_granted"])
    return granted - sum(int(entry["units"]) for entry in receipts)


def surge_day(context):
    """The first day the change log puts crawler traffic on the site."""

    days = [entry["day"] for entry in context["changes"] if entry["kind"] == "crawler_surge"]
    return min(days) if days else None


def unmeasured_slices(context, receipts):
    """Slices the archive still holds whose rows were never cleaned or counted."""

    surge = surge_day(context)
    if surge is None:
        return []
    billed = {(entry["day"], entry["arm"]) for entry in receipts}
    retained = context["archive"]["retained_from"]
    found = []
    for row in context["sessions_by_day"]:
        key = (row["day"], row["arm"])
        if row["crawler_rules"] != "off" or row["day"] < max(retained, surge):
            continue
        if key not in billed and key not in found:
            found.append(key)
    return sorted(found)
