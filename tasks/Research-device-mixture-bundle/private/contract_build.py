'A second build of the notebook, written from `full_information.md` alone.'

from __future__ import annotations


REPORT = '''"""The board pack, written to the terms the board asked for."""

from math import sqrt

from bundles.score import decide

COLUMNS = (
    "refl_a",
    "refl_b",
    "refl_c",
    "edge_density",
    "skew",
    "contrast",
    "blur",
    "tilt",
)
COVER = 1.959964
FLOOR_ROWS = 20


def as_rows(published):
    names = list(published["columns"])
    return [dict(zip(names, row)) for row in published["rows"]]


def bays(context):
    """Every unit's bay, and which conditions each bay and firmware can see."""

    seen = {}
    cells = {}
    for unit in as_rows(context["fleet_register"]):
        bay = str(unit["duty_profile"])
        seen[str(unit["unit_id"])] = bay
        for column, value in unit.items():
            if not column.startswith("share_") or float(value) <= 0.0:
                continue
            key = (bay, str(unit["firmware"]))
            cells.setdefault(key, {})[column[len("share_"):]] = float(value)
    return seen, cells


def on_the_unit(context, row):
    """The capture put back on the scale the unit itself decides on."""

    gain = float(context["firmware"]["capture_gain"])
    raised = str(row.get("stage")) == "as_captured"
    return {
        column: (
            float(row[column]) / gain
            if raised and column.startswith("refl_")
            else float(row[column])
        )
        for column in COLUMNS
    }


def counted(context, receipts):
    """Wrong and total by bay and bundle, over every field capture we hold."""

    where, _ = bays(context)
    tally = {}
    held = as_rows(context["capture_log"])
    for entry in receipts:
        held = held + [dict(row) for row in entry.get("observed", {}).get("rows", ())]
    for row in held:
        bay = where.get(str(row["device_id"]))
        if bay is None:
            continue
        raised = str(row.get("stage")) == "as_captured"
        fixed = on_the_unit(context, row) if raised else None
        for bundle in context["bundles"]:
            call = decide(bundle, fixed) if raised else int(row[bundle])
            cell = tally.setdefault((bay, bundle), [0, 0])
            cell[1] += 1
            if call != int(row["label"]):
                cell[0] += 1
    return tally


def worst(context, receipts):
    """Each bundle at the bay it serves worst, best bundle first."""

    tally = counted(context, receipts)
    out = []
    for bundle in context["bundles"]:
        found = [
            (100.0 * pair[0] / pair[1], bay, pair[1])
            for (bay, name), pair in tally.items()
            if name == bundle and pair[1]
        ]
        found.sort()
        points, bay, rows = found[-1]
        out.append((points, bundle, bay, rows))
    out.sort()
    return out


def band(points, rows):
    share = points / 100.0
    return COVER * sqrt(share * (1.0 - share) / rows) * 100.0


def analyze(context, receipts):
    order = worst(context, receipts)
    points, bundle, bay, rows = order[0]
    half = band(points, rows)
    return {
        "bundle": bundle,
        "worst_profile": bay,
        "fleet_points": points,
        "points_range": [points - half, points + half],
        "rows_used": rows,
        "bundle_points": [
            {"bundle": name, "points": value} for value, name, _, _ in order
        ],
        "requests": [
            {
                "receipt_id": entry["receipt_id"],
                "rows_returned": int(entry["rows_returned"]),
                "credits_charged": int(entry["credits_charged"]),
                "refused": entry.get("refusal") is not None,
            }
            for entry in receipts
        ],
        "credits_used": sum(int(entry["credits_charged"]) for entry in receipts),
    }


def apart(order, extra_bay, extra_rows):
    total = 0.0
    for points, _, bay, rows in order[:2]:
        held = rows + (extra_rows if bay == extra_bay else 0)
        share = points / 100.0
        total += share * (1.0 - share) / held
    return 100.0 * sqrt(total)


def next_collection(context, receipts):
    order = worst(context, receipts)
    if order[1][0] - order[0][0] > 2.0 * band(order[0][0], order[0][3]):
        return "stop"
    terms = context["annotation"]
    left = int(terms["credits_granted"]) - sum(
        int(entry["credits_charged"]) for entry in receipts
    )
    cap = int(terms["max_rows_per_request"])
    _, cells = bays(context)
    offers = []
    for _, _, bay, _ in order[:2]:
        price = int(terms["credit_cost_per_row"][bay])
        rows = min(cap, left // price)
        if rows < FLOOR_ROWS:
            continue
        gain = apart(order, "", 0) - apart(order, bay, rows)
        if gain <= apart(order, "", 0) - apart(order, "counter", cap):
            continue
        for firmware in (context["firmware"]["raised"], context["firmware"]["earlier"]):
            conditions = cells.get((bay, firmware))
            if not conditions:
                continue
            best = sorted(conditions.items(), key=lambda item: -item[1])[0][0]
            offers.append((-gain, bay, firmware, best, rows))
            break
    if not offers:
        return "stop"
    offers.sort()
    _, bay, firmware, condition, rows = offers[0]
    return {
        "duty_profile": bay,
        "firmware": firmware,
        "condition": condition,
        "rows": rows,
    }
'''


SUPPORT = '''"""Nothing lives here in this build; the pack is one module."""
'''


FILES = {"analysis.py": REPORT, "support.py": SUPPORT}
