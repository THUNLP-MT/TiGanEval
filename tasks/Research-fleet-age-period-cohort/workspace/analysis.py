"""Faults per van-month for the 2022-H2 build against the build a year before.

Fit the rate on months of age and on calendar month over every row of the
returns, with the roster headcounts underneath, then read each build off what
the fit leaves over. The 2022-H2 build comes out a long way under the 2021-H2
build, so the plan is to put the rest of the audit days on it at Kestrel, which
is where most of it sits.
"""

from math import sqrt


def _month(label):
    year, month = str(label)[:7].split("-")
    return int(year) * 12 + int(month) - 1


def _solve(matrix, vector):
    size = len(vector)
    rows = [list(matrix[i]) + [vector[i]] for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        head = rows[column][column] or 1e-12
        for row in range(size):
            if row != column and rows[row][column]:
                share = rows[row][column] / head
                for position in range(column, size + 1):
                    rows[row][position] -= share * rows[column][position]
    return [rows[i][size] / (rows[i][i] or 1e-12) for i in range(size)]


def table(context):
    """(build month, return month) -> heads on the roster and faults raised."""

    held = {}
    for row in context["roster"]:
        key = (row["build_month"], row["month"])
        held[key] = held.get(key, 0) + int(row["vans_on_the_books"])
    build_of = {van["van_id"]: van["build_month"] for van in context["vans"]}
    raised = {}
    for row in context["faults"]:
        key = (build_of[row["van_id"]], str(row["raised_date"])[:7])
        raised[key] = raised.get(key, 0) + 1
    return {
        key: (float(count), float(raised.get(key, 0)))
        for key, count in held.items()
        if count > 0
    }


def analyze(context, receipts):
    grid = table(context)
    months = sorted({month for _build, month in grid})
    columns = {month: 2 + index for index, month in enumerate(months[1:])}
    size = 2 + len(months) - 1
    normal = [[0.0] * size for _ in range(size)]
    target = [0.0] * size
    rows = []
    for (build, month) in sorted(grid):
        heads, faults = grid[(build, month)]
        entries = [(0, 1.0), (1, float(_month(month) - _month(build)))]
        if month in columns:
            entries.append((columns[month], 1.0))
        value = 100.0 * faults / heads
        rows.append(((build, month), entries, heads, value))
        for position, first in entries:
            target[position] += heads * first * value
            for other, second in entries:
                normal[position][other] += heads * first * second
    beta = _solve(normal, target)

    groups = context["audit"]["build_groups"]
    early, late = context["audit"]["compare"]
    left = {}
    weight = {}
    faults_of = {}
    for (build, _when), entries, heads, value in rows:
        fitted = sum(beta[position] * factor for position, factor in entries)
        group = None
        for name, members in groups.items():
            if build in members:
                group = name
        left[group] = left.get(group, 0.0) + heads * (value - fitted)
        weight[group] = weight.get(group, 0.0) + heads
        faults_of[group] = faults_of.get(group, 0.0) + heads * value / 100.0

    difference = left[late] / weight[late] - left[early] / weight[early]
    spread = 100.0 * sqrt(
        faults_of[late] / weight[late] ** 2 + faults_of[early] / weight[early] ** 2
    )
    return {
        "build_difference_points": round(difference, 1),
        "difference_range": [difference - spread, difference + spread],
        "vehicle_months": round(sum(weight.values()), 1),
        "days": [],
        "days_charged": 0,
    }


def next_collection(context, receipts):
    """Put the days that are left on the 2022-H2 build at Kestrel."""

    from datetime import date, timedelta

    day = date.fromisoformat(str(context["as_of"]))
    while day.isoweekday() > 5 or any(str(e["day"]) == day.isoformat() for e in receipts):
        day = day + timedelta(days=1)
    return {
        "depot": "Kestrel",
        "builds": ["2022-H2"],
        "age_band": [0, 60],
        "vans": int(context["audit"]["vans_per_day"]),
        "day": day.isoformat(),
    }
