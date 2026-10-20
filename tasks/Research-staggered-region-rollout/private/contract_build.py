'The notebooks three readers of `full_information.md` write with nothing else open.'

CONTRACT_READING = '''"""The Halcombe rollout readout, written off the board's terminal note."""

from datetime import date, timedelta
from math import erf, sqrt


def _shift(day, amount):
    return (date.fromisoformat(str(day)) + timedelta(days=int(amount))).isoformat()


def _register(context):
    return {str(row["region"]): dict(row) for row in context["register"]}


def _live(row):
    # "a metro that has not gone live by the end of that week"
    value = str(row.get("live_from") or "")
    return value or None


def _rates(context):
    # "pick one of the two stamps and read every rate as that stamp's on-time
    # count over that metro-day's sampled orders"
    out = {}
    for row in context["order_sample"]:
        total = int(row["sampled_orders"])
        if total:
            out[(str(row["region"]), str(row["date"]))] = (
                int(row["ontime_by_placed_at"]) / total,
                total,
            )
    return out


def _turned_off(context, region):
    # "The on-call log has batching disabled there at 09:40 on 11 March and it
    # never came back, so from that morning Riverbend is on neither side"
    days = [
        str(row["date"])
        for row in context.get("dispatch_incidents", ())
        if str(row.get("region")) == region and str(row.get("event")) == "disabled"
    ]
    return min(days) if days else None


def _measured(context, rows):
    # "the region book cut on 1 February and the metros on it that went live
    # inside the window closing on 20 April"
    closes = str(context["book"]["window_closes_on"])
    out = {}
    for name, orders in context["book"]["orders_on_the_count_day"].items():
        start = _live(rows.get(name, {}))
        if start is not None and start <= closes:
            out[name] = int(orders)
    return out


def _exposure(context, rows, name):
    # "Read each metro over its first 28 days on batching and no further"
    start = _live(rows[name])
    off = _turned_off(context, name)
    last = str(context["as_of"])
    days = []
    for step in range(int(context["exposure_days"])):
        day = _shift(start, step)
        if day > last or (off is not None and day >= off):
            break
        days.append(day)
    return days


def _baseline(context, rows, name):
    # "against the 28 days before it went live"
    start = _live(rows[name])
    first = str(context["window"]["first_day"])
    back = int(context["baseline_days"])
    return [
        day
        for day in (_shift(start, -step) for step in range(1, back + 1))
        if day >= first
    ]


def _controls(context, rows, name, day):
    # "the metros in that metro's own service band that had not gone live yet on
    # the day being read, whether or not the book carries them"; a metro on
    # neither side is not one either, so the pool is the register and not the book
    band = rows[name]["band"]
    out = []
    for other, row in rows.items():
        if other == name or row["band"] != band:
            continue
        start = _live(row)
        if start is not None and start <= day:
            continue
        off = _turned_off(context, other)
        if off is not None and day >= off:
            continue
        out.append(other)
    return sorted(out)


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _metro(context, rows, rates, name):
    """That metro's own move, and what the sampled orders leave open in it."""

    exposure = _exposure(context, rows, name)
    baseline = _baseline(context, rows, name)
    if not exposure or not baseline:
        return None
    seen = {}

    def rate(region, day):
        return rates.get((region, day), (0.0, 0))

    def variance(region, day, weight):
        share, count = rate(region, day)
        if count:
            seen[(region, day)] = seen.get((region, day), 0.0) + weight

    base = _mean([rate(name, day)[0] for day in baseline])
    moves = []
    for day in exposure:
        others = _controls(context, rows, name, day)
        if not others:
            continue
        theirs = _mean([
            rate(other, day)[0] - _mean([rate(other, back)[0] for back in baseline])
            for other in others
        ])
        moves.append((rate(name, day)[0] - base) - theirs)
        variance(name, day, 1.0 / len(exposure))
        for other in others:
            variance(other, day, -1.0 / (len(exposure) * len(others)))
            for back in baseline:
                variance(other, back, 1.0 / (len(exposure) * len(others) * len(baseline)))
    for day in baseline:
        variance(name, day, -1.0 / len(baseline))
    if not moves:
        return None
    spread = 0.0
    for (region, day), weight in seen.items():
        share, count = rate(region, day)
        spread += weight * weight * share * (1.0 - share) / count
    return _mean(moves), spread, len(exposure)


def _normal(target):
    low, high = -12.0, 12.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if 0.5 * (1.0 + erf(middle / sqrt(2.0))) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def analyze(context, receipts):
    rows = _register(context)
    book = _measured(context, rows)
    rates = _rates(context)
    total = sum(book.values())
    effect = 0.0
    variance = 0.0
    days = 0
    for name, orders in sorted(book.items()):
        read = _metro(context, rows, rates, name)
        if read is None:
            continue
        move, spread, count = read
        weight = orders / total
        effect += weight * move
        variance += weight * weight * spread
        days += count
    # "a range that would have been safe on all four of the networks this
    # notebook produces a readout for ... one chance in twenty across the set"
    networks = max(1, int(context.get("networks_reviewed", 4)))
    half = _normal(1.0 - 0.05 / (2.0 * networks)) * sqrt(variance) * 100.0
    effect *= 100.0
    return {
        "effect_points": round(effect, 1),
        "effect_range_points": [effect - half, effect + half],
        "metro_days": days,
        # "Every region-week the receipts carry appears in the readout exactly
        # once ... That includes the week the board handed back"
        "measurements": [
            {
                "receipt_id": entry["receipt_id"],
                "region": entry["region"],
                "week": entry["week"],
                "region_weeks_charged": entry["region_weeks_charged"],
                "days_returned": entry["days_returned"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    report = analyze(context, receipts)
    low, high = report["effect_range_points"]
    # "a stop only when the range this readout printed is already inside the
    # bar, or when there is no region-week the wave desk will serve"
    if high - low <= float(context["board_bar_points"]):
        return "stop"
    terms = context["capacity"]
    if int(terms["region_weeks_granted"]) - len(list(receipts)) < 1:
        return "stop"
    taken = {}
    charged = set()
    for entry in receipts:
        taken[str(entry["week"])] = taken.get(str(entry["week"]), 0) + 1
        charged.add((str(entry["region"]), str(entry["week"])))
    rows = _register(context)
    book = context["book"]["orders_on_the_count_day"]
    # "that band is Halcombe's, and the desk serves every network on its own
    # terms": the band comes off this network's capacity terms, never a constant
    share = int(terms["holdback_share_band"][1])
    best = None
    for week in terms["bookable_weeks"]:
        if taken.get(str(week), 0) >= int(terms["region_weeks_per_week"]):
            continue
        end = _shift(week, 6)
        for name, row in sorted(rows.items()):
            start = _live(row)
            if start is not None and start <= end:
                continue
            if int(row["orders_per_day"]) <= int(terms["minimum_orders_per_day"]):
                continue
            if (name, str(week)) in charged:
                continue
            # "what it is worth to the next board is ... how much of the book
            # that metro is"; the week to beat is the largest metro left
            key = (int(book.get(name, 0)), int(row["orders_per_day"]))
            if best is None or key > best[0]:
                best = (key, {"region": name, "week": str(week), "holdback_share": share})
    if best is None:
        return "stop"
    return best[1]
'''


COMPARISON_HELD_BUILD = '''"""The Halcombe rollout readout, netted over one map of metro-days."""

from datetime import date, timedelta
from math import erf, sqrt


def _shift(day, amount):
    return (date.fromisoformat(str(day)) + timedelta(days=int(amount))).isoformat()


def _register(context):
    return {str(row["region"]): dict(row) for row in context["register"]}


def _live(row):
    value = str(row.get("live_from") or "")
    return value or None


def _sample(context):
    # "pick one of the two stamps and read every rate as that stamp's on-time
    # count over that metro-day's sampled orders"
    out = {}
    for row in context["order_sample"]:
        total = int(row["sampled_orders"])
        if total:
            out[(str(row["region"]), str(row["date"]))] = (
                int(row["ontime_by_placed_at"]) / total,
                total,
            )
    return out


def _turned_off(context, region):
    # "from that morning Riverbend is on neither side"
    days = [
        str(row["date"])
        for row in context.get("dispatch_incidents", ())
        if str(row.get("region")) == region and str(row.get("event")) == "disabled"
    ]
    return min(days) if days else None


def _measured(context, rows):
    # "the metros on it that went live inside the window closing on 20 April"
    closes = str(context["book"]["window_closes_on"])
    out = {}
    for name, orders in context["book"]["orders_on_the_count_day"].items():
        start = _live(rows.get(name, {}))
        if start is not None and start <= closes:
            out[name] = int(orders)
    return out


def _exposure(context, rows, name):
    # "Read each metro over its first 28 days on batching and no further"
    start = _live(rows[name])
    off = _turned_off(context, name)
    last = str(context["as_of"])
    days = []
    for step in range(int(context["exposure_days"])):
        day = _shift(start, step)
        if day > last or (off is not None and day >= off):
            break
        days.append(day)
    return days


def _baseline(context, rows, name):
    # "against the 28 days before it went live"
    start = _live(rows[name])
    first = str(context["window"]["first_day"])
    back = int(context["baseline_days"])
    return [
        day
        for day in (_shift(start, -step) for step in range(1, back + 1))
        if day >= first
    ]


def _waiting(context, rows, name, day):
    # "the metros in that metro's own service band that had not gone live yet on
    # the day being read, whether or not the book carries them"
    band = rows[name]["band"]
    out = []
    for other, row in rows.items():
        if other == name or row["band"] != band:
            continue
        start = _live(row)
        if start is not None and start <= day:
            continue
        off = _turned_off(context, other)
        if off is not None and day >= off:
            continue
        out.append(other)
    return sorted(out)


def _weights(context, rows, sample):
    """One weight per metro-day, with the shared comparison metros netted once.

    The comparison metros are the ones the band still had waiting on the day
    being read, and "it is those same metros ... that are read back over its
    four weeks before", so each of them is carried back at the share it took on
    that day rather than being re-chosen against the four weeks before.
    """

    book = _measured(context, rows)
    total = sum(book.values())
    coef = {}
    days = 0

    def add(key, value):
        coef[key] = coef.get(key, 0.0) + value

    for name, orders in sorted(book.items()):
        exposure = _exposure(context, rows, name)
        baseline = _baseline(context, rows, name)
        if not exposure or not baseline:
            continue
        weight = orders / total
        span, back = len(exposure), len(baseline)
        days += span
        for day in exposure:
            add((name, day), weight / span)
        for day in baseline:
            add((name, day), -weight / back)
        for day in exposure:
            others = _waiting(context, rows, name, day)
            carried = {other: sample.get((other, day), (0.0, 0))[1] for other in others}
            seen = sum(carried.values())
            if not seen:
                continue
            for other in others:
                take = carried[other] / seen
                add((other, day), -weight * take / span)
                for base_day in baseline:
                    add((other, base_day), weight * take / (span * back))
    return coef, days


def _normal(target):
    low, high = -12.0, 12.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if 0.5 * (1.0 + erf(middle / sqrt(2.0))) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def analyze(context, receipts):
    rows = _register(context)
    sample = _sample(context)
    coef, days = _weights(context, rows, sample)
    effect = 100.0 * sum(
        value * sample[key][0] for key, value in coef.items() if key in sample
    )
    variance = 0.0
    for key, value in coef.items():
        if key not in sample:
            continue
        share, count = sample[key]
        variance += value * value * share * (1.0 - share) / count
    # "a range that would have been safe on all four of the networks this
    # notebook produces a readout for ... one chance in twenty across the set"
    networks = max(1, int(context.get("networks_reviewed", 4)))
    half = _normal(1.0 - 0.05 / (2.0 * networks)) * sqrt(variance) * 100.0
    return {
        "effect_points": round(effect, 1),
        "effect_range_points": [effect - half, effect + half],
        "metro_days": days,
        "measurements": [
            {
                "receipt_id": entry["receipt_id"],
                "region": entry["region"],
                "week": entry["week"],
                "region_weeks_charged": entry["region_weeks_charged"],
                "days_returned": entry["days_returned"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    report = analyze(context, receipts)
    low, high = report["effect_range_points"]
    # "a stop only when the range this readout printed is already inside the
    # bar, or when there is no region-week the wave desk will serve"
    if high - low <= float(context["board_bar_points"]):
        return "stop"
    terms = context["capacity"]
    if int(terms["region_weeks_granted"]) - len(list(receipts)) < 1:
        return "stop"
    taken = {}
    charged = set()
    for entry in receipts:
        taken[str(entry["week"])] = taken.get(str(entry["week"]), 0) + 1
        charged.add((str(entry["region"]), str(entry["week"])))
    rows = _register(context)
    book = context["book"]["orders_on_the_count_day"]
    # "that band is Halcombe's, and the desk serves every network on its own
    # terms": the band comes off this network's capacity terms, never a constant
    share = int(terms["holdback_share_band"][1])
    best = None
    # the last week the board is still selling, rather than the first
    for week in reversed(list(terms["bookable_weeks"])):
        if taken.get(str(week), 0) >= int(terms["region_weeks_per_week"]):
            continue
        end = _shift(week, 6)
        for name, row in sorted(rows.items()):
            start = _live(row)
            if start is not None and start <= end:
                continue
            if int(row["orders_per_day"]) <= int(terms["minimum_orders_per_day"]):
                continue
            if (name, str(week)) in charged:
                continue
            # "what it is worth to the next board is ... how much of the book
            # that metro is"
            key = (int(book.get(name, 0)), int(row["orders_per_day"]))
            if best is None or key > best[0]:
                best = (key, {"region": name, "week": str(week), "holdback_share": share})
    if best is None:
        return "stop"
    return best[1]
'''


DAILY_MEAN_BUILD = '''"""The Halcombe rollout readout, one day one reading."""

from datetime import date, timedelta
from math import erf, sqrt


def _shift(day, amount):
    return (date.fromisoformat(str(day)) + timedelta(days=int(amount))).isoformat()


def _register(context):
    return {str(row["region"]): dict(row) for row in context["register"]}


def _live(row):
    value = str(row.get("live_from") or "")
    return value or None


def _daily(context):
    # "read every rate as that stamp's on-time count over that metro-day's
    # sampled orders"
    out = {}
    for row in context["order_sample"]:
        total = int(row["sampled_orders"])
        if total:
            out[(str(row["region"]), str(row["date"]))] = (
                int(row["ontime_by_placed_at"]) / total,
                total,
            )
    return out


def _turned_off(context, region):
    days = [
        str(row["date"])
        for row in context.get("dispatch_incidents", ())
        if str(row.get("region")) == region and str(row.get("event")) == "disabled"
    ]
    return min(days) if days else None


def _in_the_book(context, rows):
    closes = str(context["book"]["window_closes_on"])
    out = {}
    for name, orders in context["book"]["orders_on_the_count_day"].items():
        start = _live(rows.get(name, {}))
        if start is not None and start <= closes:
            out[name] = int(orders)
    return out


def _four_weeks_on(context, rows, name):
    start = _live(rows[name])
    off = _turned_off(context, name)
    last = str(context["as_of"])
    days = []
    for step in range(int(context["exposure_days"])):
        day = _shift(start, step)
        if day > last or (off is not None and day >= off):
            break
        days.append(day)
    return days


def _four_weeks_before(context, rows, name):
    start = _live(rows[name])
    first = str(context["window"]["first_day"])
    back = int(context["baseline_days"])
    return [
        day
        for day in (_shift(start, -step) for step in range(1, back + 1))
        if day >= first
    ]


def _still_waiting(context, rows, name, day):
    # "whether or not the book carries them — the book decides what the number is
    # about, not what it is read against"
    band = rows[name]["band"]
    out = []
    for other, row in rows.items():
        if other == name or row["band"] != band:
            continue
        start = _live(row)
        if start is not None and start <= day:
            continue
        off = _turned_off(context, other)
        if off is not None and day >= off:
            continue
        out.append(other)
    return sorted(out)


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _reading(context, rows, daily, name):
    """One metro's move, read a day at a time on both stretches.

    "A metro's four weeks is the average of those metro-day rates, one day one
    reading, not one count over the whole stretch", and the metros its band
    still had waiting on the day being read are the ones read back over the four
    weeks before, so the comparison keeps the membership it had on that day.
    """

    on = _four_weeks_on(context, rows, name)
    before = _four_weeks_before(context, rows, name)
    if not on or not before:
        return None

    def rate(region, day):
        return daily.get((region, day), (0.0, 0))[0]

    weights = {}

    def carry(region, day, value):
        if daily.get((region, day), (0.0, 0))[1]:
            weights[(region, day)] = weights.get((region, day), 0.0) + value

    mine_after = _mean([rate(name, day) for day in on])
    mine_before = _mean([rate(name, day) for day in before])
    for day in on:
        carry(name, day, 1.0 / len(on))
    for day in before:
        carry(name, day, -1.0 / len(before))
    theirs_after = []
    theirs_before = []
    for day in on:
        others = _still_waiting(context, rows, name, day)
        if not others:
            continue
        theirs_after.append(_mean([rate(other, day) for other in others]))
        theirs_before.append(
            _mean([_mean([rate(other, back) for back in before]) for other in others])
        )
        for other in others:
            carry(other, day, -1.0 / (len(on) * len(others)))
            for back in before:
                carry(other, back, 1.0 / (len(on) * len(others) * len(before)))
    moved = (mine_after - mine_before) - (_mean(theirs_after) - _mean(theirs_before))
    spread = 0.0
    for key, value in weights.items():
        share, count = daily[key]
        spread += value * value * share * (1.0 - share) / count
    return moved, spread, len(on)


def _normal(target):
    low, high = -12.0, 12.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if 0.5 * (1.0 + erf(middle / sqrt(2.0))) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def analyze(context, receipts):
    rows = _register(context)
    book = _in_the_book(context, rows)
    daily = _daily(context)
    total = sum(book.values())
    effect = 0.0
    variance = 0.0
    days = 0
    for name, orders in sorted(book.items()):
        read = _reading(context, rows, daily, name)
        if read is None:
            continue
        moved, spread, count = read
        weight = orders / total
        effect += weight * moved
        variance += weight * weight * spread
        days += count
    networks = max(1, int(context.get("networks_reviewed", 4)))
    half = _normal(1.0 - 0.05 / (2.0 * networks)) * sqrt(variance) * 100.0
    effect *= 100.0
    return {
        "effect_points": round(effect, 1),
        "effect_range_points": [effect - half, effect + half],
        "metro_days": days,
        "measurements": [
            {
                "receipt_id": entry["receipt_id"],
                "region": entry["region"],
                "week": entry["week"],
                "region_weeks_charged": entry["region_weeks_charged"],
                "days_returned": entry["days_returned"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    report = analyze(context, receipts)
    low, high = report["effect_range_points"]
    if high - low <= float(context["board_bar_points"]):
        return "stop"
    terms = context["capacity"]
    if int(terms["region_weeks_granted"]) - len(list(receipts)) < 1:
        return "stop"
    rows = _register(context)
    book = context["book"]["orders_on_the_count_day"]
    # "that band is Halcombe's, and the desk serves every network on its own
    # terms": the band comes off this network's capacity terms, never a constant
    share = int(terms["holdback_share_band"][1])
    taken = {}
    charged = set()
    for entry in receipts:
        taken[str(entry["week"])] = taken.get(str(entry["week"]), 0) + 1
        charged.add((str(entry["region"]), str(entry["week"])))
    offers = []
    for week in terms["bookable_weeks"]:
        if taken.get(str(week), 0) >= int(terms["region_weeks_per_week"]):
            continue
        end = _shift(week, 6)
        for name, row in rows.items():
            start = _live(row)
            if start is not None and start <= end:
                continue
            if int(row["orders_per_day"]) <= int(terms["minimum_orders_per_day"]):
                continue
            if (name, str(week)) in charged:
                continue
            offers.append(
                (int(book.get(name, 0)), int(row["orders_per_day"]), str(week), name)
            )
    if not offers:
        return "stop"
    offers.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    carried, _orders, week, name = offers[0]
    return {"region": name, "week": week, "holdback_share": share}
'''


CONTRACT_BUILDS = (
    (
        "the mean of the metro-day rates, the comparison held at the exposure day",
        {"analysis.py": CONTRACT_READING,
         "support.py": '"""Nothing the notebook needs lives here."""\n'},
    ),
    (
        "the comparison netted over one map, weighted by the sampled orders it carried",
        {"analysis.py": COMPARISON_HELD_BUILD,
         "support.py": '"""Nothing the notebook needs lives here."""\n'},
    ),
    (
        "one day one reading, each stretch written out as a mean of daily rates",
        {"analysis.py": DAILY_MEAN_BUILD,
         "support.py": '"""Nothing the notebook needs lives here."""\n'},
    ),
)
