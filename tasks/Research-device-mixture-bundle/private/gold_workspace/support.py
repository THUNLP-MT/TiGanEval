"""Reading a fleet's evidence: which bay a capture came from, what the unit
saw when it decided, and how much of each bay the campaign has annotated."""

from math import sqrt

from bundles.score import decide

COVER = 1.96
FEATURES = (
    "refl_a",
    "refl_b",
    "refl_c",
    "edge_density",
    "skew",
    "contrast",
    "blur",
    "tilt",
)
REFLECTANCE = ("refl_a", "refl_b", "refl_c")


_HELD = {}


def table(published):
    """One published table as a list of dictionaries, kept between calls."""

    key = ("table", id(published), len(published.get("rows", ())))
    if key not in _HELD:
        columns = list(published.get("columns", ()))
        _HELD[key] = [
            {column: row[index] for index, column in enumerate(columns)}
            for row in published.get("rows", ())
        ]
    return _HELD[key]


def register(context):
    return table(context["fleet_register"])


def bay_of(context):
    """Which duty profile each unit works in, off the register."""

    return {str(unit["unit_id"]): str(unit["duty_profile"]) for unit in register(context)}


def profiles(context):
    """The duty profiles the register has units in, biggest first."""

    counts = {}
    for unit in register(context):
        counts[str(unit["duty_profile"])] = counts.get(str(unit["duty_profile"]), 0) + 1
    return sorted(counts, key=lambda name: (-counts[name], name))


def desk_rows(receipts):
    """The annotated captures the desk sent back, bay by bay."""

    bays = ("counter", "backroom", "yard", "night")
    rows = []
    for entry in receipts:
        for row in entry.get("observed", {}).get("rows", ()):
            if str(row.get("duty_profile")) in bays:
                rows.append(row)
    return rows


def field_rows(context, receipts):
    """Every field capture a build holds: the export, plus what the desk sent back.

    A bench row is a target on a stand rather than a unit in a bay, so it
    carries no duty profile and takes no part in a fleet's number.
    """

    bays = bay_of(context)
    rows = []
    for row in table(context["capture_log"]):
        row = dict(row)
        row["duty_profile"] = bays.get(str(row["device_id"]))
        if row["duty_profile"]:
            rows.append(row)
    return rows + [dict(row) for row in desk_rows(receipts)]


def in_service(context, row):
    """The eight columns as the unit itself hands them to a bundle.

    A row the exporter wrote as it left the sensor still carries the unit's own
    capture gain on the reflectance windows; the unit takes it off before it
    decides, so a reading of that row has to take it off too.
    """

    values = [float(row[name]) for name in FEATURES]
    if str(row.get("stage")) == "as_captured":
        gain = float(context["firmware"]["capture_gain"])
        for index in range(len(REFLECTANCE)):
            values[index] = values[index] / gain
    return {name: values[index] for index, name in enumerate(FEATURES)}


def wrong(context, row, bundle):
    """Whether the bundle would have got this capture wrong on the unit."""

    if str(row.get("stage")) == "as_captured":
        return decide(bundle, in_service(context, row)) != int(row["label"])
    return int(row[bundle]) != int(row["label"])


def _tally(context, rows, bays):
    counted = {
        bundle: {profile: [0, 0] for profile in bays} for bundle in context["bundles"]
    }
    for row in rows:
        profile = row["duty_profile"]
        for bundle in context["bundles"]:
            cell = counted[bundle][profile]
            cell[1] += 1
            if wrong(context, row, bundle):
                cell[0] += 1
    return counted


def export_tally(context):
    """The export's own counts, which do not change while the campaign runs."""

    key = ("export", id(context))
    if key not in _HELD:
        bays = bay_of(context)
        rows = []
        for row in table(context["capture_log"]):
            profile = bays.get(str(row["device_id"]))
            if profile:
                row = dict(row)
                row["duty_profile"] = profile
                rows.append(row)
        _HELD[key] = _tally(context, rows, profiles(context))
    return _HELD[key]


def points_by_profile(context, receipts):
    """Points of error per bundle per duty profile, and the rows behind each."""

    base = export_tally(context)
    added = _tally(context, desk_rows(receipts), profiles(context))
    return {
        bundle: {
            profile: {
                "points": 100.0
                * (base[bundle][profile][0] + added[bundle][profile][0])
                / (base[bundle][profile][1] + added[bundle][profile][1]),
                "rows": base[bundle][profile][1] + added[bundle][profile][1],
            }
            for profile in bays
            if base[bundle][profile][1] + added[bundle][profile][1]
        }
        for bundle, bays in base.items()
    }


def worst_bay(measured):
    """The bay a bundle serves worst, and what it costs there."""

    profile = max(measured, key=lambda name: measured[name]["points"])
    return profile, measured[profile]["points"], measured[profile]["rows"]


def ranking(context, receipts):
    """Every bundle with its worst bay's points, best first."""

    measured = points_by_profile(context, receipts)
    ranked = []
    for bundle, bays in measured.items():
        profile, points, rows = worst_bay(bays)
        ranked.append(
            {"bundle": bundle, "worst_profile": profile, "points": points, "rows": rows}
        )
    ranked.sort(key=lambda entry: (entry["points"], entry["bundle"]))
    return ranked


def spread(points, rows):
    """How far the number could still move on the rows behind that bay."""

    share = points / 100.0
    return COVER * sqrt(share * (1.0 - share) / max(1, rows)) * 100.0


def requests(receipts):
    return [
        {
            "receipt_id": entry["receipt_id"],
            "rows_returned": int(entry["rows_returned"]),
            "credits_charged": int(entry["credits_charged"]),
            "refused": bool(entry.get("refusal")),
        }
        for entry in receipts
    ]


def credits_used(receipts):
    return sum(int(entry["credits_charged"]) for entry in receipts)


def credits_left(context, receipts):
    return int(context["annotation"]["credits_granted"]) - credits_used(receipts)


def cells_with_units(context, profile, firmware):
    """The conditions the register says that bay sees on that firmware, biggest first."""

    seen = {}
    for unit in register(context):
        if str(unit["duty_profile"]) != profile or str(unit["firmware"]) != firmware:
            continue
        for condition in ("bright", "dim", "glare", "damaged"):
            share = float(unit.get(f"share_{condition}", 0.0))
            if share > 0.0:
                seen[condition] = max(seen.get(condition, 0.0), share)
    return sorted(seen, key=lambda name: -seen[name])


def separation(context, receipts, profile, rows):
    """How much closer the top two stand once those rows come back."""

    order = ranking(context, receipts)[:2]

    def apart(extra):
        total = 0.0
        for entry in order:
            held = entry["rows"] + (extra if entry["worst_profile"] == profile else 0)
            share = entry["points"] / 100.0
            total += share * (1.0 - share) / max(1, held)
        return 100.0 * sqrt(total)

    return apart(0) - apart(rows)
