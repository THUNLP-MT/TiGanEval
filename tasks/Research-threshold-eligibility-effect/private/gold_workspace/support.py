"""Helpers for the offer campaign notebook."""

from datetime import date
from math import erf, exp, sqrt


def days_between(first, last):
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def run_scores(context):
    """The score each account carried on the day its run decided the offer.

    The register keeps whatever a refresh left behind. Where the refresh landed
    after the run had already put an offer in front of the account, the score
    the run saw is the one the recompute log kept.
    """

    before = {
        str(row["account_id"]): (str(row["refresh_date"]), float(row["score_before"]))
        for row in context["recompute"]
    }
    scores = {}
    for row in context["register"]:
        account = str(row["account_id"])
        score = float(row["standing_score"])
        entry = before.get(account)
        if entry and row["offer_date"] and entry[0] > str(row["offer_date"]):
            score = entry[1]
        scores[account] = score
    return scores


def credit_lifted(row, score, cut):
    """True when a filed credit, and not the line, put this account over it."""

    credit = float(row["credits_filed"])
    return credit > 0 and score >= cut > score - credit


def reviewed_files(receipts):
    """The files the desk returned, by account, with their own watched days."""

    files = {}
    for entry in receipts:
        for row in entry.get("files") or ():
            files[str(row["account_id"])] = row
    return files


def near_cut_rows(context, receipts, band=5.0):
    """The accounts the line decided, each with its orders and its days at risk.

    The run's own score puts an account on a side and inside the band; accounts
    the run passed over belong to neither side; an account a credit carried
    over the line is not one the line decided. A file the desk has since
    reviewed is counted on the days that review watched it for.
    """

    cut = float(context["cut"])
    scores = run_scores(context)
    files = reviewed_files(receipts)
    rows = []
    for row in context["register"]:
        if row["run_status"] != "scored":
            continue
        account = str(row["account_id"])
        score = scores[account]
        if abs(score - cut) > band or credit_lifted(row, score, cut):
            continue
        seen = files.get(account, row)
        start = str(row["offer_date"])
        last = str(seen["last_observed_date"]) or start
        ordered = bool(seen["first_order_date"])
        watched = days_between(start, seen["first_order_date"] if ordered else last)
        if watched <= 0 and not ordered:
            continue
        rows.append((1 if int(row["offer_flag"]) else 0, ordered, max(0, watched)))
    return rows


def person_time(rows):
    """Per side, the orders the campaign saw and the days it watched for them."""

    tally = {0: [0, 0], 1: [0, 0]}
    for side, ordered, watched in rows:
        entry = tally[side]
        entry[0] += 1 if ordered else 0
        entry[1] += watched
    return tally


def sixty_day_rate(events, days, window):
    """A rate measured over days watched, read back as a sixty-day chance."""

    if days <= 0:
        return 0.0
    return 1.0 - exp(-window * (events / days))


def standard_error(tally, window):
    """How far the difference of the two sides' chances could still move."""

    total = 0.0
    for side in (0, 1):
        events, days = tally[side]
        if events <= 0 or days <= 0:
            return float("inf")
        hazard = events / days
        rate = sixty_day_rate(events, days, window)
        total += ((1.0 - rate) * window * hazard) ** 2 / events
    return sqrt(total)


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


def range_multiplier(context):
    """What a range has to carry to hold on every market the slide counts.

    The council allows one time in twenty over the run of markets on the slide,
    and this report is one of them, so the chance is divided among them.
    """

    markets = max(1, int(context["council"]["markets_on_the_slide"]))
    return _inverse_normal(1.0 - 0.05 / (2.0 * markets))


def files_left(context, receipts):
    granted = int(context["review_grant"]["files_granted"])
    return granted - sum(int(entry["files_charged"]) for entry in receipts)


def week_with_most_files(context, receipts=(), band=5.0):
    """The run week whose available files add the most watching at the line."""

    cut = float(context["cut"])
    scores = run_scores(context)
    pulled = reviewed_files(receipts)
    today = date.fromisoformat(str(context["as_of"]))
    window = int(context["order_window_days"])
    by_week = {}
    for row in context["register"]:
        if row["run_status"] != "scored":
            continue
        account = str(row["account_id"])
        if account in pulled:
            continue
        score = scores[account]
        if abs(score - cut) > band:
            continue
        start = date.fromisoformat(str(row["offer_date"]))
        current = date.fromisoformat(
            str(row["first_order_date"] or row["last_observed_date"])
        )
        through = min(today, start.fromordinal(start.toordinal() + window))
        gain = max(0, (through - current).days)
        entry = by_week.setdefault(int(row["run_week"]), [0, 0])
        entry[0 if score >= cut else 1] += gain
    usable = {week: min(pair) for week, pair in by_week.items() if min(pair) > 0}
    return max(usable, key=lambda week: usable[week]) if usable else None
