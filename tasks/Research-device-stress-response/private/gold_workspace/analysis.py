"""Where one in ten of the QR-40 family leak at the plan's hold, and what to
put in front of the chamber desk next.

The console is not the gauge. Each bench writes a pressure through its own
factor, and the dead-weight block that goes on at each batch's ends is what
says by how much; every row is put back into the gauge's bar with its own
batch's pair of block readings before it joins a level.

The rows that came back sitting on the console's sticker figure are not
pressures. They say the cartridge was at least that and nothing more, so they
carry no level and are left out.

The plan is written against thirty minutes. A row held for five sits at a
different place on the same family, so it is not a row of this ladder whatever
cartridge it names, and the hold column is what decides that rather than the
label.
"""

from support import (
    bracketing,
    counted_rows,
    crossing,
    half_width,
    hours_left,
    ladder,
    bench_is_out,
    next_day,
    readable_cartridges,
    stores_left,
    unit_rows,
)


def analyze(context, receipts):
    levels = ladder(context, receipts)
    value = crossing(levels)
    spread = half_width(levels)
    return {
        "crossing_bar": value,
        "crossing_range_bar": [value - spread, value + spread],
        "counted_units": _counted_units(context, receipts),
        "sessions": [
            {
                "booking_id": entry["booking_id"],
                "bench": entry["bench"],
                "dwell_min": int(entry["dwell_min"]),
                "units": int(entry["units_returned"]),
                "leaks": list(entry.get("results") or ()).count("leak"),
                "hours_charged": float(entry["hours_charged"]),
            }
            for entry in receipts
        ],
    }


def _counted_units(context, receipts):
    """The couplings behind the number, split by where they came from."""

    totals = {}
    for row in counted_rows(context, receipts):
        entry = totals.setdefault(str(row["source"]), [0, 0])
        entry[0] += 1
        entry[1] += 1 if str(row["result"]) == "leak" else 0
    return [
        {"source": source, "units": units, "leaks": leaks}
        for source, (units, leaks) in sorted(totals.items())
    ]


def next_block(context, receipts):
    """The hours go where the crossing is, at the hold the plan is written for.

    An hour is charged whether or not the sheet runs, so the session has to be
    one the desk will take: a bench that is on that day, a batch the stores can
    fill, the ports full and no more than the ports. What it buys is units at
    the two levels the crossing sits between; a level further out is already
    decided, and the cartridge the console pins returns the sticker figure
    instead of a pressure.
    """

    hold = int(context["plan_hold_min"])
    cost = float(context["budget"]["hours_at_the_plan_hold"])
    day = next_day(context, receipts)
    stock = stores_left(context, receipts)
    if hours_left(context, receipts) < cost or day is None:
        return "stop"
    if not stock or max(stock.values()) < 1:
        return "stop"
    benches = [
        name for name in sorted(context["benches"])
        if not bench_is_out(context, name, day)
    ]
    if not benches:
        return "stop"
    batch = max(sorted(stock), key=lambda name: stock[name])
    units = min(int(context["budget"]["ports_per_session"]), stock[batch])
    wanted = [
        name for name in bracketing(context, receipts)
        if name in readable_cartridges(context)
    ]
    if not wanted:
        return "stop"
    counted = {}
    for row in counted_rows(context, receipts):
        counted[str(row["cartridge"])] = counted.get(str(row["cartridge"]), 0) + 1
    cartridge = min(wanted, key=lambda name: (counted.get(name, 0), name))
    return {
        "bench": benches[0],
        "batch": batch,
        "cartridge": cartridge,
        "dwell_min": hold,
        "units": int(units),
    }
