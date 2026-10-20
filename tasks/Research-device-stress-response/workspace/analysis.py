"""Where one in ten of the QR-40 family leak, off the March run table.

Leak fraction for each cartridge against what the console wrote for it, a
straight line through the six of them, and the pressure where that line reaches
one in ten. The range comes off how far the six points sit from the line. The
hours that are left go on C-300, which is where the leaks are.
"""

CARTRIDGES = ("C-140", "C-200", "C-215", "C-255", "C-275", "C-300")
TARGET = 0.10


def analyze(context, receipts):
    points = ladder(context)
    slope, intercept = straight_line(points)
    crossing = (TARGET - intercept) / slope
    spread = 2.0 * scatter(points, slope, intercept) / abs(slope)
    return {
        "crossing_bar": crossing,
        "crossing_range_bar": [crossing - spread, crossing + spread],
        "counted_units": [],
        "sessions": [],
    }


def ladder(context):
    """(mean console reading, leak fraction, units) for each cartridge run."""

    table = {}
    for row in context["runs"]:
        if row["result"] not in ("leak", "hold"):
            continue
        entry = table.setdefault(row["cartridge"], [0.0, 0, 0])
        entry[0] += float(row["reading_bar"])
        entry[1] += 1
        entry[2] += 1 if row["result"] == "leak" else 0
    return [
        (total / units, leaks / units, units)
        for total, units, leaks in table.values()
        if units
    ]


def straight_line(points):
    """Least squares through the ladder, each cartridge weighted by its units."""

    weight = sum(units for _bar, _fraction, units in points)
    mean_bar = sum(bar * units for bar, _fraction, units in points) / weight
    mean_fraction = sum(f * units for _bar, f, units in points) / weight
    top = sum(
        units * (bar - mean_bar) * (f - mean_fraction) for bar, f, units in points
    )
    bottom = sum(units * (bar - mean_bar) ** 2 for bar, _f, units in points)
    slope = top / bottom
    return slope, mean_fraction - slope * mean_bar


def scatter(points, slope, intercept):
    """How far the cartridges sit from the line, in leak fraction."""

    weight = sum(units for _bar, _f, units in points)
    return (
        sum(units * (f - (intercept + slope * bar)) ** 2 for bar, f, units in points)
        / weight
    ) ** 0.5


def next_block(context, receipts):
    """The hours that are left go on the top cartridge, where the leaks are."""

    return {
        "bench": "B-1",
        "batch": "B-05",
        "cartridge": "C-300",
        "dwell_min": context["plan_hold_min"],
        "units": context["budget"]["ports_per_session"],
    }
