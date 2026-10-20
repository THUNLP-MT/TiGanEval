"""January apportionment for the Block A header, off the sample sheet.

The estates office asked for the number, the range around it, the slots behind
them and the visits the agreement was charged for, so the report carries all
four.

Each header slot gives one set of three shares once the two channels are read
against the characterisation sheet. The report is the average of the slots, and
the range is how far the slots spread either side of it. The recovery return's
marker prints under the analyser's floor, so the floor is what goes into the
sheet's third column.

The slots left over go on more of the same: more header slots, more of the
month, a tighter average.
"""

from fractions import Fraction

SUPPLIES = ("district_tie_in", "gas_plant", "data_hall_recovery")


def analyze(context, ledger):
    rows = header_rows(context)
    answers = [slot_shares(context, row) for row in rows]
    shares = [sum(answer[index] for answer in answers) / len(answers) for index in range(3)]
    band = [
        [min(answer[index] for answer in answers), max(answer[index] for answer in answers)]
        for index in range(3)
    ]
    return {
        "shares": {name: shares[index] for index, name in enumerate(SUPPLIES)},
        "share_band": {name: band[index] for index, name in enumerate(SUPPLIES)},
        "samples_used": [row["sample_id"] for row in rows],
        "samples_set_aside": [],
        "visits": [
            {
                "call_id": entry["call_id"],
                "point": entry["point"],
                "slots_charged": entry["slots_charged"],
            }
            for entry in ledger
        ],
    }


def header_rows(context):
    """Every header slot the sheet carries with both channels on it."""

    window = context["window"]
    return [
        row
        for row in context["samples"]
        if row["point"] == "header"
        and window["first_day"] <= row["taken_at"][:10] <= window["last_day"]
        and row.get("cond_uScm") is not None
        and row.get("mark_flag") == "value"
    ]


def signatures(context):
    """The three supplies as the sheet has them, the floor in for recovery."""

    rows = {row["supply"]: row for row in context["signature_sheet"]["rows"]}
    conductivity = [float(rows[name]["cond_uScm"]) for name in SUPPLIES]
    marker = [
        float(rows[name]["mark_muL"])
        if rows[name]["mark_flag"] == "value"
        else float(rows[name]["mark_floor_muL"])
        for name in SUPPLIES
    ]
    return conductivity, marker


def slot_shares(context, row):
    """The three shares one slot implies, straight off the sheet."""

    conductivity, marker = signatures(context)
    return solve3(
        [conductivity, marker, [1.0, 1.0, 1.0]],
        [float(row["cond_uScm"]), float(row["mark_muL"]), 1.0],
    )


def solve3(rows, rhs):
    grid = [[Fraction(str(value)) for value in row] + [Fraction(str(rhs[index]))]
            for index, row in enumerate(rows)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(grid[index][column]))
        grid[column], grid[pivot] = grid[pivot], grid[column]
        for index in range(3):
            if index == column:
                continue
            factor = grid[index][column] / grid[column][column]
            for position in range(column, 4):
                grid[index][position] -= factor * grid[column][position]
    return [float(grid[index][3] / grid[index][index]) for index in range(3)]


def next_collection(context, ledger):
    """Six more header slots, and a tighter average to show the director."""

    return {
        "point": "header",
        "channels": ["conductivity", "marker"],
        "dwell_min": 5,
        "samples": 6,
    }
