'A second notebook, written from `full_information.md` and from nothing else.'

from __future__ import annotations


ANALYSIS = '''"""EM-9 soak report, built from the review contract.

A module's start is what the incoming sheet read it at. A bench row sitting on
the meter's full scale says the module was at least that bright and carries no
reading, so it is dropped; the reference source's own rows are not a module's.
Hours are wall clock: the export writes `elapsed_h` out of the sample index at
an hour a sample, and each rack's stamps say what one step of that column is
worth on that rack.

Every catalogue law then goes through the rows. How far a curve sits from the
rows is taken at one drive and case at a time, over the rows at that setting
and no others, so a corner a block has just returned rows at is read on its own
weight rather than against everything the campaign already held. A law stands
while every setting with eight rows or more behind it comes back inside half
again the meter's repeat spread and it reaches a tenth at all. The figure is
the middle of what the standing laws answer; the range carries how far apart
they are, and never less than three standard errors off the counted rows, which
is the whole of it once one law is left standing.
"""

from datetime import datetime
from math import exp, isfinite, log, log1p, sqrt

SOURCES = ("trace_export", "receipt")
BAR = 1.5
LEAST_ROWS = 8
ERRORS = 3.0
SHARE = 0.5


def _shape(entry, hours):
    kind = entry["time_shape"]
    constant = float(entry["shape_constant"])
    hours = max(float(hours), 0.0)
    if kind == "power":
        return hours ** constant
    if kind == "logarithmic":
        return log1p(hours / constant)
    if kind == "saturating":
        return 1.0 - exp(-hours / constant)
    return hours / constant


def _hours_at(entry, level):
    kind = entry["time_shape"]
    constant = float(entry["shape_constant"])
    if level <= 0.0:
        return float("inf")
    if kind == "power":
        return level ** (1.0 / constant)
    if kind == "logarithmic":
        return constant * (exp(min(level, 700.0)) - 1.0)
    if kind == "saturating":
        return float("inf") if level >= 1.0 else -constant * log(1.0 - level)
    return level * constant


def _stress(entry, context, drive, temp):
    field = float(context["field_drive_a"])
    constant = float(entry["drive_constant"])
    if entry["drive_form"] == "exponential":
        by_drive = exp(constant * (float(drive) - field))
    else:
        by_drive = (float(drive) / field) ** constant
    step = (float(temp) - float(context["hold_temp_c"])) / 10.0
    return by_drive * float(entry["ten_degree_factor"]) ** step


def _step_worth(context):
    """What one step of `elapsed_h` is worth in wall-clock hours, rack by rack."""

    seen = {}
    worth = {}
    for row in context["traces"]:
        key = (str(row["rack"]), str(row["module_id"]))
        stamp = datetime.fromisoformat(str(row["logged_at"]))
        column = float(row["elapsed_h"])
        if key in seen:
            was_column, was_stamp = seen[key]
            gap = column - was_column
            if gap > 0:
                hours = (stamp - was_stamp).total_seconds() / 3600.0
                worth.setdefault(key[0], hours / gap)
        seen[key] = (column, stamp)
    return worth


def rows(context, receipts):
    """Every row that carries a reading, in wall-clock hours and lost milliwatts."""

    worth = _step_worth(context)
    start = {}
    for item in context["modules"]:
        start[str(item["module_id"])] = float(item["incoming_mw"])
    top = float(context["meter_full_scale_mw"])
    out = []
    for row in context["traces"]:
        name = str(row["module_id"])
        if name not in start or float(row["output_mw"]) >= top - 1e-9:
            continue
        out.append(
            (
                name,
                float(row["elapsed_h"]) * worth.get(str(row["rack"]), 1.0),
                float(row["drive_a"]),
                float(context["hold_temp_c"]),
                start[name],
                float(row["output_mw"]),
                "trace_export",
            )
        )
    for entry in receipts:
        incoming = {}
        for item in entry.get("modules") or ():
            incoming[str(item["module_id"])] = float(item["incoming_mw"])
        for reading in entry.get("readings") or ():
            if float(reading["output_mw"]) >= top - 1e-9:
                continue
            name = str(reading["module_id"])
            out.append(
                (
                    name,
                    float(reading["soak_h"]),
                    float(entry["drive_a"]),
                    float(entry["case_temp_c"]),
                    incoming[name],
                    float(reading["output_mw"]),
                    "receipt",
                )
            )
    return out


def _folded(context, entry, counted):
    """One design point per module and hour, so the fit is not row order."""

    table = {}
    for name, hours, drive, temp, begin, output, _source in counted:
        soak = hours * _stress(entry, context, drive, temp)
        key = (name, round(hours, 6), round(drive, 4), round(temp, 3))
        cell = table.setdefault(key, [0.0, 0.0, 0.0, (drive, temp)])
        cell[0] += begin * _shape(entry, soak)
        cell[1] += begin - output
        cell[2] += 1.0
    return table


def fitted(context, entry, counted):
    """The one amplitude the rows leave, and how far the curve sits from them."""

    table = _folded(context, entry, counted)
    top = bottom = 0.0
    for design, lost, count, _setting in table.values():
        top += (design / count) * (lost / count) * count
        bottom += (design / count) ** 2 * count
    amplitude = top / bottom if bottom > 0 else 0.0
    groups = {}
    for design, lost, count, setting in table.values():
        gap = lost / count - amplitude * (design / count)
        cell = groups.setdefault(setting, [0.0, 0])
        cell[0] += gap * gap * count
        cell[1] += int(count)
    worst = 0.0
    for total, count in groups.values():
        if count >= LEAST_ROWS:
            worst = max(worst, sqrt(total / count))
    return amplitude, bottom, worst


def read(context, receipts):
    counted = rows(context, receipts)
    catalogue = context["catalogue"]
    table = {}
    for name in sorted(catalogue):
        amplitude, weight, worst = fitted(context, catalogue[name], counted)
        table[name] = (amplitude, weight, worst)
    bar = BAR * float(context["meter_read_spread_mw"])
    target = float(context["target_loss"])

    def figure(name, amplitude):
        if amplitude <= 0.0:
            return float("inf")
        return _hours_at(catalogue[name], target / amplitude)

    standing = []
    for name in sorted(table):
        if table[name][2] <= bar and isfinite(figure(name, table[name][0])):
            standing.append(name)
    if not standing:
        standing = [min(sorted(table), key=lambda name: table[name][2])]
    figures = sorted(figure(name, table[name][0]) for name in standing)
    errors = []
    for name in standing:
        amplitude, weight, worst = table[name]
        spread = max(worst, float(context["meter_read_spread_mw"]))
        error = spread / sqrt(weight) if weight > 0 else 0.0
        step = max(amplitude * 1e-4, 1e-15)
        slope = (figure(name, amplitude + step) - figure(name, amplitude - step)) / (2 * step)
        errors.append(abs(slope) * ERRORS * error)
    middle = sum(figures) / len(figures)
    return {
        "standing": standing,
        "hours": middle,
        "floor": max(figures[-1] - figures[0], max(errors)),
        "counted": counted,
    }


def analyze(context, receipts):
    answer = read(context, receipts)
    floor = answer["floor"]
    totals = {}
    for name, _hours, _drive, _temp, _begin, _output, source in answer["counted"]:
        cell = totals.setdefault(source, [0, set()])
        cell[0] += 1
        cell[1].add(name)
    return {
        "hours_to_loss": answer["hours"],
        "hours_range": [answer["hours"] - floor, answer["hours"] + floor],
        "standing_laws": answer["standing"],
        "counted_rows": [
            {"source": source, "rows": count, "modules": len(names)}
            for source, (count, names) in sorted(totals.items())
        ],
        "blocks": [
            {
                "block_id": entry["block_id"],
                "drive_a": float(entry["drive_a"]),
                "case_temp_c": float(entry["case_temp_c"]),
                "ports": int(entry["ports_asked"]),
                "modules": int(entry["modules_returned"]),
                "rows": int(entry["rows_returned"]),
                "days_charged": int(entry["days_charged"]),
            }
            for entry in receipts
        ],
    }


def _left(context, receipts):
    days = int(context["budget"]["chamber_days_granted"])
    spares = {}
    for lot, count in context["spares"].items():
        spares[lot] = int(count)
    for entry in receipts:
        days -= int(entry["days_charged"])
        lot = str(entry.get("lot") or "")
        if lot in spares:
            spares[lot] -= int(entry.get("modules_returned") or 0)
    return days, spares


def _takes(context, receipts, booking):
    budget = context["budget"]
    days, spares = _left(context, receipts)
    if not 1 <= booking["ports"] <= int(budget["ports_per_block"]):
        return False
    if not int(budget["smallest_block_days"]) <= booking["chamber_days"] <= int(
        budget["days_per_block"]
    ):
        return False
    if booking["drive_a"] < float(budget["lowest_drive_a"]) - 1e-9:
        return False
    if booking["drive_a"] > float(budget["highest_drive_a"]) + 1e-9:
        return False
    if booking["case_temp_c"] < float(context["hold_temp_c"]) - 1e-9:
        return False
    if booking["case_temp_c"] > float(budget["highest_case_temp_c"]) + 1e-9:
        return False
    if spares.get(booking["lot"], 0) < booking["ports"]:
        return False
    if days < booking["chamber_days"]:
        return False
    schedule = list(context["campaign_days"])
    used = sum(int(entry["days_charged"]) for entry in receipts)
    run = schedule[used : used + booking["chamber_days"]]
    if len(run) < booking["chamber_days"]:
        return False
    shut = list(context["rig_out_of_service"])
    return not any(shut and str(shut[0]) <= day <= str(shut[1]) for day in run)


def _apart(context, answer, booking):
    """How far apart a block would drive the two laws that fit this build best."""

    catalogue = context["catalogue"]
    order = sorted(answer["table"], key=lambda name: answer["table"][name][2])
    if len(order) < 2:
        return 0.0
    top = float(context["meter_full_scale_mw"])
    begin = float(context["spares_incoming_mw"][booking["lot"]])
    step = float(context["budget"]["block_reading_every_h"])
    total = 0.0
    hours = step
    while hours <= booking["chamber_days"] * 24.0 + 1e-9:
        seen = []
        for name in order[:2]:
            entry = catalogue[name]
            soak = hours * _stress(entry, context, booking["drive_a"], booking["case_temp_c"])
            seen.append(min(begin * (1.0 - answer["table"][name][0] * _shape(entry, soak)), top))
        total += booking["ports"] * (seen[0] - seen[1]) ** 2
        hours += step
    return sqrt(total) / float(context["meter_read_spread_mw"])


def next_block(context, receipts):
    budget = context["budget"]
    answer = read(context, receipts)
    counted = answer["counted"]
    catalogue = context["catalogue"]
    answer["table"] = {}
    for name in sorted(catalogue):
        answer["table"][name] = fitted(context, catalogue[name], counted)
    days, spares = _left(context, receipts)
    if days < int(budget["smallest_block_days"]):
        return "stop"
    if not spares or max(spares.values()) < 1:
        return "stop"
    if 2.0 * answer["floor"] <= float(budget["range_the_review_acts_on_h"]):
        return "stop"
    best = None
    score = 0.0
    lots = sorted(spares)
    steps = int(round((float(budget["highest_drive_a"]) - float(budget["lowest_drive_a"])) / 0.05))
    for lot in lots:
        #: The contract: a block draws from one lot and takes every port that
        #: lot can fill, up to the ports the rig holds, because the days are
        #: charged whatever is in the rig.
        ports = min(int(budget["ports_per_block"]), spares[lot])
        if ports < 1:
            continue
        for run in range(int(budget["days_per_block"]), 0, -1):
            for tick in range(steps + 1):
                drive = round(float(budget["lowest_drive_a"]) + 0.05 * tick, 3)
                for degree in range(0, 11):
                    temp = round(float(context["hold_temp_c"]) + degree, 2)
                    if temp > float(budget["highest_case_temp_c"]) + 1e-9:
                        continue
                    booking = {
                        "drive_a": drive,
                        "case_temp_c": temp,
                        "ports": ports,
                        "chamber_days": run,
                        "lot": lot,
                    }
                    if not _takes(context, receipts, booking):
                        continue
                    value = _apart(context, answer, booking)
                    if value > score + 1e-9:
                        best, score = booking, value
    if best is None or score <= 0.0:
        return "stop"
    return best
'''

SUPPORT = '"""Nothing here: this build keeps everything in analysis.py."""\n'

FILES = {"analysis.py": ANALYSIS, "support.py": SUPPORT}
