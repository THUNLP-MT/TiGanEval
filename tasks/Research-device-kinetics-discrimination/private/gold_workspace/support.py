"""Helpers for the EM-9 soak notebook."""

from datetime import datetime
from math import exp, isfinite, log, log1p, sqrt

#: A law is left standing while its own curve sits inside half again the
#: meter's repeat spread at every setting the campaign has rows for, and a
#: setting with fewer rows than this behind it decides nothing either way.
STANDS_FACTOR = 1.5
MIN_GROUP_ROWS = 8
#: The range is never printed tighter than the standing laws leave it, nor
#: tighter than three standard errors off the rows counted.
ERROR_MULTIPLE = 3.0
#: A block earns its days when it drives the two best-fitting laws at least
#: this far apart, against the best block the plan still allows.
PARTING_SHARE = 0.5


# -- the catalogue's shapes -------------------------------------------------


def shape(entry, hours):
    kind = str(entry["time_shape"])
    constant = float(entry["shape_constant"])
    hours = max(float(hours), 0.0)
    if kind == "power":
        return hours ** constant
    if kind == "logarithmic":
        return log1p(hours / constant)
    if kind == "saturating":
        return 1.0 - exp(-hours / constant)
    return hours / constant


def hours_at(entry, loss):
    """The soak hours at which one law reaches this share of output lost."""

    kind = str(entry["time_shape"])
    constant = float(entry["shape_constant"])
    if loss <= 0:
        return float("inf")
    if kind == "power":
        return loss ** (1.0 / constant)
    if kind == "logarithmic":
        return constant * (exp(min(loss, 700.0)) - 1.0)
    if kind == "saturating":
        return float("inf") if loss >= 1.0 else -constant * log(1.0 - loss)
    return loss * constant


def stress(entry, context, drive_a, case_temp_c):
    """How much faster one law says a module ages at this drive and case."""

    field = float(context["field_drive_a"])
    hold = float(context["hold_temp_c"])
    constant = float(entry["drive_constant"])
    if str(entry["drive_form"]) == "exponential":
        drive = exp(constant * (float(drive_a) - field))
    else:
        drive = (float(drive_a) / field) ** constant
    return drive * float(entry["ten_degree_factor"]) ** ((float(case_temp_c) - hold) / 10.0)


# -- the rows the campaign holds --------------------------------------------


def _moment(value):
    return datetime.fromisoformat(str(value))


def hours_per_sample(context):
    """What one step of `elapsed_h` is worth in wall-clock hours, rack by rack.

    The export writes `elapsed_h` out of the logger's sample index at an hour a
    sample. A rack whose logger runs on another profile therefore carries a
    column that does not keep the rack's own clock, and the stamps say by how
    much.
    """

    ends = {}
    for row in context["traces"]:
        key = (str(row["rack"]), str(row["module_id"]))
        stamp = (float(row["elapsed_h"]), _moment(row["logged_at"]))
        first, last = ends.get(key, (stamp, stamp))
        ends[key] = (min(first, stamp), max(last, stamp))
    factor = {}
    for (rack, _module), (first, last) in sorted(ends.items()):
        steps = last[0] - first[0]
        if steps <= 0 or rack in factor:
            continue
        factor[rack] = (last[1] - first[1]).total_seconds() / 3600.0 / steps
    return factor


def trace_rows(context):
    """Every module row of the export, in wall-clock hours and the meter's mW.

    A row the reference source wrote is not a module. A row sitting on the
    meter's full scale says the module was at least there and does not say
    where, so it carries no reading. Where a module started is what the
    incoming sheet read it at, not its first bench row.
    """

    factor = hours_per_sample(context)
    incoming = {
        str(item["module_id"]): float(item["incoming_mw"]) for item in context["modules"]
    }
    span = float(context["meter_full_scale_mw"]) - 1e-9
    rows = []
    for row in context["traces"]:
        name = str(row["module_id"])
        if name == str(context["reference_module_id"]) or name not in incoming:
            continue
        if float(row["output_mw"]) >= span:
            continue
        rows.append(
            {
                "module_id": name,
                "hours": float(row["elapsed_h"]) * factor.get(str(row["rack"]), 1.0),
                "drive_a": float(row["drive_a"]),
                "case_temp_c": float(context["hold_temp_c"]),
                "start_mw": incoming[name],
                "output_mw": float(row["output_mw"]),
                "source": "trace_export",
            }
        )
    return rows


def receipt_rows(context, receipts):
    """Every module row a chamber block returned that carries a reading."""

    span = float(context["meter_full_scale_mw"]) - 1e-9
    rows = []
    for entry in receipts:
        incoming = {
            str(item["module_id"]): float(item["incoming_mw"])
            for item in entry.get("modules") or ()
        }
        for reading in entry.get("readings") or ():
            if float(reading["output_mw"]) >= span:
                continue
            rows.append(
                {
                    "module_id": str(reading["module_id"]),
                    "hours": float(reading["soak_h"]),
                    "drive_a": float(entry["drive_a"]),
                    "case_temp_c": float(entry["case_temp_c"]),
                    "start_mw": incoming[str(reading["module_id"])],
                    "output_mw": float(reading["output_mw"]),
                    "source": "receipt",
                }
            )
    return rows


def counted_rows(context, receipts):
    return trace_rows(context) + receipt_rows(context, receipts)


# -- putting every catalogue law through those rows -------------------------


def fit(context, entry, rows):
    """One law's amplitude and how far it sits from the rows, setting by setting."""

    top = bottom = 0.0
    prepared = []
    for row in rows:
        soak = float(row["hours"]) * stress(entry, context, row["drive_a"], row["case_temp_c"])
        design = float(row["start_mw"]) * shape(entry, soak)
        lost = float(row["start_mw"]) - float(row["output_mw"])
        top += design * lost
        bottom += design * design
        prepared.append((row, design, lost))
    amplitude = top / bottom if bottom > 0 else 0.0
    groups = {}
    for row, design, lost in prepared:
        key = (round(float(row["drive_a"]), 3), round(float(row["case_temp_c"]), 2))
        groups.setdefault(key, []).append(lost - amplitude * design)
    spread = {
        key: sqrt(sum(value * value for value in values) / len(values))
        for key, values in groups.items()
    }
    worst = max(
        (value for key, value in spread.items() if len(groups[key]) >= MIN_GROUP_ROWS),
        default=0.0,
    )
    return {"amplitude": amplitude, "design_sum": bottom, "worst_spread_mw": worst}


def crossing(context, entry, amplitude):
    """Hours at the field drive and the hold at which that law reaches the target."""

    if amplitude <= 0:
        return float("inf")
    return hours_at(entry, float(context["target_loss"]) / amplitude)


def reading(context, receipts):
    """The standing laws, the figure they agree on and the floor under a range."""

    rows = counted_rows(context, receipts)
    catalogue = context["catalogue"]
    table = {name: fit(context, catalogue[name], rows) for name in sorted(catalogue)}
    bar = STANDS_FACTOR * float(context["meter_read_spread_mw"])
    standing = sorted(
        name for name, item in table.items() if item["worst_spread_mw"] <= bar
    )
    #: A law that never reaches the target at all on the rows so far leaves no
    #: figure to stand up, so it drops out while another law still gives one.
    reaches = [
        name
        for name in standing
        if isfinite(crossing(context, catalogue[name], table[name]["amplitude"]))
    ]
    standing = reaches or standing
    if not standing:
        reaching = [
            name
            for name in table
            if isfinite(crossing(context, catalogue[name], table[name]["amplitude"]))
        ]
        standing = [
            min(reaching or sorted(table), key=lambda name: table[name]["worst_spread_mw"])
        ]
    figures = sorted(
        crossing(context, catalogue[name], table[name]["amplitude"]) for name in standing
    )
    errors = []
    for name in standing:
        item = table[name]
        spread = max(item["worst_spread_mw"], float(context["meter_read_spread_mw"]))
        error = spread / sqrt(item["design_sum"]) if item["design_sum"] > 0 else 0.0
        low = crossing(context, catalogue[name], item["amplitude"] + ERROR_MULTIPLE * error)
        high = crossing(
            context, catalogue[name], max(item["amplitude"] - ERROR_MULTIPLE * error, 1e-12)
        )
        errors.append(abs(high - low) / 2.0)
    return {
        "standing": standing,
        "hours": sum(figures) / len(figures),
        "floor": max(figures[-1] - figures[0], max(errors)),
        "rows": rows,
        "table": table,
    }


# -- the chamber's own arithmetic -------------------------------------------


def days_left(context, receipts):
    granted = int(context["budget"]["chamber_days_granted"])
    return granted - sum(int(entry["days_charged"]) for entry in receipts)


def spares_left(context, receipts):
    left = {lot: int(count) for lot, count in context["spares"].items()}
    for entry in receipts:
        lot = str(entry.get("lot") or "")
        if lot in left:
            left[lot] -= int(entry.get("modules_returned") or 0)
    return left


def rig_is_out(context, day):
    window = list(context["rig_out_of_service"])
    return bool(window) and str(window[0]) <= str(day) <= str(window[1])


def block_days(context, receipts, days):
    """The schedule days one block of this length would run over."""

    schedule = list(context["campaign_days"])
    start = sum(int(entry["days_charged"]) for entry in receipts)
    return schedule[start : start + int(days)]


def feasible(context, receipts, booking):
    """Whether the desk would take this sheet, by the plan's own terms."""

    budget = context["budget"]
    ports = int(booking["ports"])
    days = int(booking["chamber_days"])
    if not 1 <= ports <= int(budget["ports_per_block"]):
        return False
    if not 1 <= days <= int(budget["days_per_block"]):
        return False
    if not float(budget["lowest_drive_a"]) - 1e-9 <= float(booking["drive_a"]) <= float(
        budget["highest_drive_a"]
    ) + 1e-9:
        return False
    if not float(context["hold_temp_c"]) - 1e-9 <= float(booking["case_temp_c"]) <= float(
        budget["highest_case_temp_c"]
    ) + 1e-9:
        return False
    if spares_left(context, receipts).get(str(booking["lot"]), 0) < ports:
        return False
    if days_left(context, receipts) < days:
        return False
    run = block_days(context, receipts, days)
    return len(run) == days and not any(rig_is_out(context, day) for day in run)


def spare_readings(context, read, booking):
    """What the two best-fitting laws each expect that block's rows to read."""

    catalogue = context["catalogue"]
    pair = sorted(read["table"], key=lambda name: read["table"][name]["worst_spread_mw"])[:2]
    if len(pair) < 2:
        return []
    span = float(context["meter_full_scale_mw"])
    base = float(context["spares_incoming_mw"][str(booking["lot"])])
    step = float(context["budget"]["block_reading_every_h"])
    out = []
    hours = step
    while hours <= float(booking["chamber_days"]) * 24.0 + 1e-9:
        pair_loss = [
            read["table"][name]["amplitude"]
            * shape(
                catalogue[name],
                hours * stress(catalogue[name], context, booking["drive_a"],
                               booking["case_temp_c"]),
            )
            for name in pair
        ]
        out.append([min(base * (1.0 - value), span) for value in pair_loss])
        hours += step
    return out


def parting(context, read, booking):
    """How far apart one block would drive those two laws, in meter spreads."""

    total = 0.0
    for low, high in spare_readings(context, read, booking):
        total += int(booking["ports"]) * (low - high) ** 2
    return sqrt(total) / float(context["meter_read_spread_mw"])


def candidate_blocks(context, receipts):
    """Every block the plan's own terms still allow, on a grid of its settings."""

    budget = context["budget"]
    low = float(budget["lowest_drive_a"])
    high = float(budget["highest_drive_a"])
    hold = float(context["hold_temp_c"])
    top = float(budget["highest_case_temp_c"])
    drives = [round(low + 0.1 * step, 2) for step in range(int(round((high - low) / 0.1)) + 1)]
    temps = [round(hold + 2.5 * step, 1) for step in range(int(round((top - hold) / 2.5)) + 1)]
    left = spares_left(context, receipts)
    out = []
    for lot in sorted(left):
        ports = min(int(budget["ports_per_block"]), left[lot])
        if ports < 1:
            continue
        for days in range(1, int(budget["days_per_block"]) + 1):
            for drive in drives:
                for temp in temps:
                    booking = {
                        "drive_a": drive,
                        "case_temp_c": temp,
                        "ports": ports,
                        "chamber_days": days,
                        "lot": lot,
                    }
                    if feasible(context, receipts, booking):
                        out.append(booking)
    return out
