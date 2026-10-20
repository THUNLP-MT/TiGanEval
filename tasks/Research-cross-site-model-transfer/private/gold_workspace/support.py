"""Reading a centre's evidence: who was reviewed, who was never shown, and how
much of the stream each of them is."""

from math import sqrt

COVER = 1.96


def counter_totals(context):
    """Received, queued and passed over, added up over the whole window."""

    received = queued = passed = 0
    for row in context["intake_counters"]:
        received += int(row["received"])
        queued += int(row["queued"])
        passed += int(row["skipped_no_history_panel"])
    return {"received": received, "queued": queued, "passed_over": passed}


def bands(context):
    """The prior-contact bands the intake counters split the stream into.

    The reviewer form renders a history panel from a fixed number of prior
    contacts, and the counters count each side of that. A centre whose form
    needs no panel has one band and it is the whole stream.
    """

    threshold = int(context["intake"]["history_panel_from_contact"])
    totals = counter_totals(context)
    received = totals["received"] or 1
    if threshold <= 0 or totals["passed_over"] == 0:
        return [
            {
                "prior_contacts_min": None,
                "prior_contacts_max": None,
                "share_of_received": totals["received"] / received,
                "shown_to_reviewers": True,
            }
        ]
    return [
        {
            "prior_contacts_min": None,
            "prior_contacts_max": threshold - 1,
            "share_of_received": totals["passed_over"] / received,
            "shown_to_reviewers": False,
        },
        {
            "prior_contacts_min": threshold,
            "prior_contacts_max": None,
            "share_of_received": totals["queued"] / received,
            "shown_to_reviewers": True,
        },
    ]


def rows_of(ledger):
    return [row for entry in ledger for row in entry.get("observed", {}).get("rows", ())]


def rows_in(ledger, low, high):
    kept = []
    for row in rows_of(ledger):
        contacts = int(row["prior_contacts"])
        if low is not None and contacts < int(low):
            continue
        if high is not None and contacts > int(high):
            continue
        kept.append(row)
    return kept


def error_of(rows):
    if not rows:
        return None
    wrong = sum(
        1 for row in rows if int(row["pipeline_decision"]) != int(row["reviewed_label"])
    )
    return wrong / len(rows)


def groups(context, ledger):
    """One entry per band: its share of received, and what the reviews say of it."""

    found = []
    for band in bands(context):
        rows = rows_in(ledger, band["prior_contacts_min"], band["prior_contacts_max"])
        found.append(
            {
                "prior_contacts_min": band["prior_contacts_min"],
                "prior_contacts_max": band["prior_contacts_max"],
                "share_of_received": band["share_of_received"],
                "error": error_of(rows),
                "rows_reviewed": len(rows),
            }
        )
    return found


def combined(groups_found):
    """The bands put back together in the proportions the counters give."""

    weight = 0.0
    total = 0.0
    for group in groups_found:
        if group["error"] is None:
            continue
        weight += group["share_of_received"]
        total += group["share_of_received"] * group["error"]
    if weight <= 0.0:
        return None
    return total / weight


def half_width(groups_found):
    """Half the unclipped width supported by the rows bought.

    A band with reviews behind it moves by its own sampling spread. A band
    with a share of the stream and no reviews at all is not narrowed by
    anything, so half its share is added straight on.
    """

    variance = 0.0
    unread = 0.0
    for group in groups_found:
        share = group["share_of_received"]
        rows = group["rows_reviewed"]
        rate = group["error"]
        if share <= 0.0:
            continue
        if rate is None or rows <= 0:
            unread += share
            continue
        variance += share * share * rate * (1.0 - rate) / rows
    return COVER * sqrt(variance) + unread * 0.5


def range_bounds(groups_found):
    """A two-sided sampling range plus every possible unread contribution."""

    point = 0.0
    variance = 0.0
    unread = 0.0
    for group in groups_found:
        share = group["share_of_received"]
        rows = group["rows_reviewed"]
        rate = group["error"]
        if share <= 0.0:
            continue
        if rate is None or rows <= 0:
            unread += share
            continue
        point += share * rate
        variance += share * share * rate * (1.0 - rate) / rows
    spread = COVER * sqrt(variance)
    return [max(0.0, point - spread), min(1.0, point + spread + unread)]


def units_used(ledger):
    return sum(int(entry["units_charged"]) for entry in ledger)


def units_left(context, ledger):
    return int(context["review"]["units_granted"]) - units_used(ledger)


def reviews(ledger):
    return [
        {
            "receipt_id": entry["receipt_id"],
            "channel": entry["channel"],
            "rows_returned": int(entry["n_returned"]),
            "units_charged": int(entry["units_charged"]),
        }
        for entry in ledger
    ]


def unseen_band(context):
    """The band this centre's queue never puts in front of a reviewer."""

    for band in bands(context):
        if not band["shown_to_reviewers"]:
            return band
    return None
