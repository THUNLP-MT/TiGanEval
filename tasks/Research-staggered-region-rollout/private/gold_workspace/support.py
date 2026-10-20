"""Helpers for the Halcombe rollout notebook."""

from datetime import date, timedelta
from math import erf, sqrt


def shift(day, amount):
    return (date.fromisoformat(str(day)) + timedelta(days=int(amount))).isoformat()


def register(context):
    """The rollout register, keyed by metro."""

    return {str(row["region"]): dict(row) for row in context["register"]}


def live_from(row):
    value = str(row.get("live_from") or "")
    return value or None


def sample_rates(context):
    """(metro, day) -> the on-time share of that day's sampled orders.

    Both stamps are on every sampled row, so one of them can be read on every
    day of the window whether or not that metro's stack had moved.
    """

    out = {}
    for row in context["order_sample"]:
        total = int(row["sampled_orders"])
        if total:
            out[(str(row["region"]), str(row["date"]))] = (
                int(row["ontime_by_placed_at"]) / total,
                total,
            )
    return out


def disabled_on(context, region):
    """The morning a metro went back to the old flow, if the log says one did."""

    days = [
        str(row["date"])
        for row in context.get("dispatch_incidents", ())
        if str(row.get("region")) == region and str(row.get("event")) == "disabled"
    ]
    return min(days) if days else None


def exposure_days(context, rows, region):
    """A metro's first days on batching, stopping if it went back to the old flow."""

    start = live_from(rows[region])
    if start is None:
        return []
    length = int(context["exposure_days"])
    last = str(context["as_of"])
    stop = disabled_on(context, region)
    days = []
    for step in range(length):
        day = shift(start, step)
        if day > last or (stop is not None and day >= stop):
            break
        days.append(day)
    return days


def baseline_days(context, rows, region):
    """The four weeks before that metro went live."""

    start = live_from(rows[region])
    first = str(context["window"]["first_day"])
    length = int(context["baseline_days"])
    days = [shift(start, -step) for step in range(1, length + 1)]
    return [day for day in reversed(days) if day >= first]


def waiting_controls(context, rows, region, day):
    """Same band, not live on that day, and not a metro sent back to the old flow."""

    band = rows[region]["band"]
    out = []
    for name, row in rows.items():
        if name == region or row["band"] != band:
            continue
        start = live_from(row)
        if start is not None and start <= day:
            continue
        stop = disabled_on(context, name)
        if stop is not None and day >= stop:
            continue
        out.append(name)
    return sorted(out)


def weights(context, rows):
    """The book's metros that went live inside the window, and what they carry."""

    closes = str(context["book"]["window_closes_on"])
    orders = context["book"]["orders_on_the_count_day"]
    out = {}
    for name, count in orders.items():
        start = live_from(rows.get(name, {}))
        if start is not None and start <= closes:
            out[name] = int(count)
    total = sum(out.values())
    return {name: count / total for name, count in out.items()}


def coefficients(context):
    """How much each metro-day's sampled rate weighs in the network's reading."""

    rows = register(context)
    share = weights(context, rows)
    coef = {}

    def add(key, value):
        coef[key] = coef.get(key, 0.0) + value

    for name, weight in sorted(share.items()):
        exposure = exposure_days(context, rows, name)
        baseline = baseline_days(context, rows, name)
        if not exposure or not baseline:
            continue
        span, back = len(exposure), len(baseline)
        for day in exposure:
            add((name, day), weight / span)
        for day in baseline:
            add((name, day), -weight / back)
        for day in exposure:
            others = waiting_controls(context, rows, name, day)
            if not others:
                continue
            for other in others:
                add((other, day), -weight / (span * len(others)))
                for base_day in baseline:
                    add((other, base_day), weight / (span * len(others) * back))
    return coef


def reading(context, coef=None):
    """The book-weighted effect on on-time share, in points."""

    rates = sample_rates(context)
    coef = coefficients(context) if coef is None else coef
    return 100.0 * sum(
        value * rates[key][0] for key, value in coef.items() if key in rates
    )


def metro_days(context):
    rows = register(context)
    return sum(
        len(exposure_days(context, rows, name)) for name in sorted(weights(context, rows))
    )


def spread(context, coef=None):
    """What the sampled orders leave open in the reading, as a standard error."""

    rates = sample_rates(context)
    coef = coefficients(context) if coef is None else coef
    total = 0.0
    for key, value in coef.items():
        if key not in rates:
            continue
        share, count = rates[key]
        total += value * value * share * (1.0 - share) / count
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


def network_multiplier(context):
    """What a range has to carry to hold on every network this file runs.

    The board's one chance in twenty is over the whole set of networks the same
    notebook is read on, so the chance is divided among them.
    """

    count = max(1, int(context.get("networks_reviewed", 4)))
    return _inverse_normal(1.0 - 0.05 / (2.0 * count))


def weeks_left(context, receipts):
    granted = int(context["capacity"]["region_weeks_granted"])
    return granted - len(list(receipts))


def eligible_weeks(context, receipts):
    """Every region-week the wave board would serve, with what the book carries.

    A week is out if the metro is live before it ends, if the metro is under the
    order floor, or if the board has already filled that week. The held-back
    share goes to the top of the band the board allows: the week is worth what
    the thinner of its two arms carries.
    """

    rows = register(context)
    capacity = context["capacity"]
    low, high = (int(value) for value in capacity["holdback_share_band"])
    cap = int(capacity["region_weeks_per_week"])
    orders = context["book"]["orders_on_the_count_day"]
    taken = {}
    charged = set()
    for entry in receipts:
        taken[str(entry["week"])] = taken.get(str(entry["week"]), 0) + 1
        charged.add((str(entry["region"]), str(entry["week"])))
    out = []
    for week in capacity["bookable_weeks"]:
        if taken.get(str(week), 0) >= cap:
            continue
        end = shift(week, 6)
        for name, row in sorted(rows.items()):
            start = live_from(row)
            if start is not None and start <= end:
                continue
            if int(row["orders_per_day"]) <= int(capacity["minimum_orders_per_day"]):
                continue
            if (name, str(week)) in charged:
                continue
            out.append(
                {
                    "region": name,
                    "week": str(week),
                    "holdback_share": high,
                    "book_orders": int(orders.get(name, 0)),
                    "orders_per_day": int(row["orders_per_day"]),
                }
            )
    return out
