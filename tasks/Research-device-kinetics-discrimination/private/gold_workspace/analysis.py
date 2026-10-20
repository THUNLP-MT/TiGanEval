"""How long an EM-9 holds at the field drive, and what to put in the chamber next.

Where a module started is what the incoming sheet read it at. The bench meter
stops at the sticker on its front and every module comes off the line above
that, so the opening rows of every trace read the sticker exactly; a row there
says the module was at least that bright and does not say where, so it carries
no reading and is left out. The 20 mW reference source read at every session
sits well under the sticker and comes back honest, which is how the sticker
rows are read for what they are.

Hours are wall clock. The export writes `elapsed_h` out of the logger's sample
index at an hour a sample, so a rack whose logger runs on another profile
carries a column that does not keep its own clock; the `logged_at` stamps say
what one step of that column is worth.

Every law in the catalogue goes to the corrected rows. More than one of them
sits inside the meter's repeat spread on the settings the campaign has, so the
report names those that stand, takes the figure they agree on, and prints a
range that carries how far apart they still are.
"""

from support import (
    PARTING_SHARE,
    candidate_blocks,
    days_left,
    feasible,
    parting,
    reading,
    spares_left,
)


def analyze(context, receipts):
    read = reading(context, receipts)
    value = read["hours"]
    floor = read["floor"]
    return {
        "hours_to_loss": value,
        "hours_range": [value - floor, value + floor],
        "standing_laws": read["standing"],
        "counted_rows": _counted_rows(read["rows"]),
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


def _counted_rows(rows):
    """The rows behind the figure, split by where they came from."""

    totals = {}
    for row in rows:
        entry = totals.setdefault(str(row["source"]), [0, set()])
        entry[0] += 1
        entry[1].add(str(row["module_id"]))
    return [
        {"source": source, "rows": count, "modules": len(modules)}
        for source, (count, modules) in sorted(totals.items())
    ]


def next_block(context, receipts):
    """The days go where the standing laws part, at settings the desk will take.

    The days are charged whether or not the sheet runs, so the block has to be
    one the desk takes: inside the supply and the chamber's own range, out of a
    lot the shop can fill, with the ports full and clear of the rig's service
    days. What it buys is rows at settings the campaign has never held, because
    the laws that fit its own rows part nowhere inside them.
    """

    budget = context["budget"]
    read = reading(context, receipts)
    if days_left(context, receipts) < int(budget["smallest_block_days"]):
        return "stop"
    if max(spares_left(context, receipts).values(), default=0) < 1:
        return "stop"
    if 2.0 * read["floor"] <= float(budget["range_the_review_acts_on_h"]):
        return "stop"
    scored = [
        (parting(context, read, booking), booking)
        for booking in candidate_blocks(context, receipts)
    ]
    if not scored:
        return "stop"
    best = max(value for value, _booking in scored)
    if best <= 0.0:
        return "stop"
    return max(
        (booking for value, booking in scored if value >= best - 1e-9),
        key=lambda booking: (int(booking["ports"]), -int(booking["chamber_days"])),
    )
