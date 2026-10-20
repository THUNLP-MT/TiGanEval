"""The working parts of the fleet note: exposure, cards, standards, the fit."""

import calendar
from datetime import date, timedelta
from statistics import NormalDist


def month_key(label):
    year, month = str(label)[:7].split("-")
    return int(year) * 12 + int(month) - 1


def month_label(key):
    return "%04d-%02d" % (key // 12, key % 12 + 1)


def month_length(label):
    year, month = str(label)[:7].split("-")
    return calendar.monthrange(int(year), int(month))[1]


def months_of(context):
    first = month_key(context["window"]["first_return"])
    last = month_key(context["window"]["last_return"])
    return [month_label(key) for key in range(first, last + 1)]


# -- what a depot raised faults under ---------------------------------------


def card_periods(context):
    """(depot, month) -> the walkaround card in force there that month."""

    out = {}
    for row in context["cards"]:
        first = month_key(row["from_month"])
        last = month_key(row["to_month"]) if row.get("to_month") else month_key("2100-01")
        out[(row["depot"], first, last)] = row["walkaround_ref"]
    return out


def card_at(periods, depot, month):
    key = month_key(month)
    for (name, first, last), ref in periods.items():
        if name == depot and first <= key <= last:
            return ref
    return None


def base_card(context):
    """The card every depot was raising faults under when the window opened."""

    rows = sorted(context["cards"], key=lambda row: (row["from_month"], row["depot"]))
    return rows[0]["walkaround_ref"] if rows else None


def current_cards(context):
    """Depot -> the card it raises faults under now."""

    periods = card_periods(context)
    last = context["window"]["last_return"]
    return {depot: card_at(periods, depot, last) for depot in context["depots"]}


# -- days on the fleet, and faults raised -----------------------------------


def card_table(context):
    """(depot, return month) -> the card that depot raised faults under."""

    periods = card_periods(context)
    return {
        (depot, month): card_at(periods, depot, month)
        for depot in context["depots"]
        for month in months_of(context)
    }


def exposure(context):
    """(build month, return month, card) -> vehicle-months on the fleet."""

    cards = card_table(context)
    window = months_of(context)
    edges = {
        month: (month_length(month), "%s-01" % month,
                "%s-%02d" % (month, month_length(month)))
        for month in window
    }
    opens, closes = month_key(window[0]), month_key(window[-1])
    out = {}
    for van in context["vans"]:
        service = str(van["in_service_date"])
        gone = str(van["off_fleet_date"])
        move = str(van.get("transfer_date") or "")
        for step in range(max(opens, month_key(service)), min(closes, month_key(gone)) + 1):
            month = month_label(step)
            length, first, last = edges[month]
            start = service if service > first else first
            end = gone if gone < last else last
            if start > end:
                continue
            if move and start < move <= end:
                before_move = (
                    date.fromisoformat(move) - timedelta(days=1)
                ).isoformat()
                spans = (
                    (van["depot"], start, before_move),
                    (van["transfer_depot"], move, end),
                )
            elif move and move <= start:
                spans = ((van["transfer_depot"], start, end),)
            else:
                spans = ((van["depot"], start, end),)
            for depot, run_start, run_end in spans:
                days = (date.fromisoformat(run_end) - date.fromisoformat(run_start)).days + 1
                if days <= 0:
                    continue
                key = (van["build_month"], month, cards[(depot, month)])
                out[key] = out.get(key, 0.0) + days / length
    return out


def faults(context):
    """(build month, return month, card) -> faults raised."""

    build_of = {van["van_id"]: van["build_month"] for van in context["vans"]}
    out = {}
    for row in context["faults"]:
        month = str(row["raised_date"])[:7]
        key = (build_of[row["van_id"]], month, row["walkaround_ref"])
        out[key] = out.get(key, 0) + 1
    return out


def card_factors(context, months, raised):
    """What each card books against the card the region started on.

    Read on the vans both cards saw: the same build months in the same return
    months, weighted the same on each side.
    """

    base = base_card(context)
    others = {ref for (_b, _m, ref) in months if ref != base}
    factors = {base: 1.0}
    for ref in sorted(others):
        top = 0.0
        bottom = 0.0
        for (build, month, name) in months:
            if name != ref:
                continue
            here = months[(build, month, ref)]
            there = months.get((build, month, base), 0.0)
            if here < 2.0 or there < 2.0:
                continue
            weight = min(here, there)
            top += weight * raised.get((build, month, ref), 0) / here
            bottom += weight * raised.get((build, month, base), 0) / there
        factors[ref] = top / bottom if bottom > 0 else 1.0
    return factors


def cells(context):
    """(build month, return month) -> vehicle-months and faults on one scale."""

    months = exposure(context)
    raised = faults(context)
    factors = card_factors(context, months, raised)
    out = {}
    for (build, month, ref), value in months.items():
        entry = out.setdefault((build, month), [0.0, 0.0])
        entry[0] += value
        entry[1] += raised.get((build, month, ref), 0) / factors.get(ref, 1.0)
    return {key: tuple(value) for key, value in out.items() if value[0] > 1e-9}


# -- which build months are one standard ------------------------------------


def standards(context):
    """Build month -> the standard it came off the line to.

    A change order takes effect in a build month and stands until the next one,
    so the build months between two orders carry one body spec and one set of
    lots.
    """

    sheets = sorted(context["build_sheets"], key=lambda row: row["build_month"])
    out = {}
    label = None
    seen = None
    for row in sheets:
        mark = (row["body_spec"], tuple(row["lots"]))
        if mark != seen:
            label = row["build_month"]
            seen = mark
        out[row["build_month"]] = label
    return out


def half_year(build_month):
    year, month = str(build_month)[:7].split("-")
    return "%s-H%d" % (year, 1 if int(month) <= 6 else 2)


# -- the fit ----------------------------------------------------------------


def _solve(matrix, vector):
    size = len(vector)
    rows = [list(matrix[index]) + [vector[index]] for index in range(size)]
    scale = max((abs(value) for row in rows for value in row[:size]), default=0.0)
    # A pivot this far under the size of the numbers going in is a direction the
    # rows do not fix, not a small number: say so rather than carrying the
    # rounding error into a variance and taking the root of a negative one.
    limit = 1e-9 * scale if scale > 0.0 else 1e-12
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        head = rows[column][column]
        if abs(head) <= limit:
            raise ValueError("the fit has nothing to separate two of its terms")
        for row in range(size):
            if row == column:
                continue
            share = rows[row][column] / head
            if share:
                for position in range(column, size + 1):
                    rows[row][position] -= share * rows[column][position]
    return [rows[index][size] / rows[index][index] for index in range(size)]


def _design(context):
    """Sparse rows of the fit, one a cell, and the name of each column."""

    grid = cells(context)
    months = months_of(context)
    keyed = standards(context)
    names = ["intercept", "age"] + ["month:%s" % month for month in months[1:]]
    order = []
    for build in sorted(keyed):
        if keyed[build] not in order:
            order.append(keyed[build])
    columns = {}
    for label in order[1:]:
        columns["build:%s" % label] = len(names)
        names.append("build:%s" % label)
    month_columns = {month: 2 + index for index, month in enumerate(months[1:])}
    rows = []
    for (build, month) in sorted(grid):
        held, raised = grid[(build, month)]
        entries = [(0, 1.0), (1, float(month_key(month) - month_key(build)))]
        if month in month_columns:
            entries.append((month_columns[month], 1.0))
        column = columns.get("build:%s" % keyed[build])
        if column is not None:
            entries.append((column, 1.0))
        rows.append((entries, held, 100.0 * raised / held))
    return rows, names, keyed


def _contrast(context, names, keyed):
    early, late = context["audit"]["compare"]
    groups = context["audit"]["build_groups"]
    built = {}
    for van in context["vans"]:
        built[van["build_month"]] = built.get(van["build_month"], 0) + 1
    index = {name: position for position, name in enumerate(names)}
    vector = [0.0] * len(names)
    for sign, group in ((1.0, late), (-1.0, early)):
        members = groups[group]
        total = sum(built.get(build, 0) for build in members)
        for build in members:
            column = index.get("build:%s" % keyed[build])
            if column is not None:
                vector[column] += sign * built.get(build, 0) / total
    return vector


def level(context):
    regions = max(1, int(context["review"]["regions_on_the_note"]))
    chance = 1.0 / float(context["review"]["one_time_in"])
    return NormalDist().inv_cdf(1.0 - chance / (2.0 * regions))


def fit(context):
    """The build difference, the half width it carries, and the months behind it."""

    rows, names, keyed = _design(context)
    size = len(names)
    normal = [[0.0] * size for _ in range(size)]
    target = [0.0] * size
    for entries, weight, value in rows:
        for position, first in entries:
            target[position] += weight * first * value
            for other, second in entries:
                normal[position][other] += weight * first * second
    beta = _solve(normal, target)
    vector = _contrast(context, names, keyed)
    spread = 0.0
    for entries, weight, value in rows:
        fitted = sum(beta[position] * factor for position, factor in entries)
        spread += weight * (value - fitted) ** 2
    spread /= max(1, len(rows) - size)
    solved = _solve(normal, vector)
    variance = spread * sum(vector[index] * solved[index] for index in range(size))
    return {
        "difference": sum(vector[index] * beta[index] for index in range(size)),
        "half_width": level(context) * variance**0.5,
        "vehicle_months": sum(weight for _entries, weight, _value in rows),
    }


# -- the audit's own day ----------------------------------------------------


def days_charged(receipts):
    return sum(int(entry["days_charged"]) for entry in receipts)


def days_left(context, receipts):
    return int(context["audit"]["days_granted"]) - days_charged(receipts)


def cards_read(receipts):
    return {
        entry["walkaround_ref"]
        for entry in receipts
        if not entry.get("refusal") and entry.get("walkaround_ref")
    }


def open_cards(context, receipts):
    return set(current_cards(context).values()) - cards_read(receipts)


def week_of(day):
    year, week, _ = date.fromisoformat(str(day)).isocalendar()
    return "%04d-W%02d" % (year, week)


def free_days(context, receipts):
    booked = {}
    used = set()
    for entry in receipts:
        used.add(str(entry["day"]))
        key = week_of(entry["day"])
        booked[key] = booked.get(key, 0) + 1
    start = date.fromisoformat(str(context["as_of"]))
    out = []
    for step in range(70):
        day = (start + timedelta(days=step)).isoformat()
        if date.fromisoformat(day).isoweekday() > 5:
            continue
        if day in used or booked.get(week_of(day), 0) >= int(context["audit"]["days_per_week"]):
            continue
        out.append(day)
    return out


def in_service(context, depot, builds, band, day):
    """The vans a day at that depot could walk round."""

    month = month_key(day)
    wanted = set(builds)
    held = []
    for van in context["vans"]:
        if half_year(van["build_month"]) not in wanted:
            continue
        if not (str(van["in_service_date"]) <= str(day) <= str(van["off_fleet_date"])):
            continue
        where = van["depot"]
        move = str(van.get("transfer_date") or "")
        if move and move <= str(day):
            where = van["transfer_depot"]
        if where != depot:
            continue
        age = month - month_key(van["build_month"])
        if band[0] <= age <= band[1]:
            held.append(van)
    return held
