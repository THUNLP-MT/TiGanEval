'The notebook a reader of `full_information.md` writes with nothing else open.'

CONTRACT_READING = '''"""The desk's planning notebook, written off the terminal contract."""

from math import exp, sqrt

_MEMO = {}
_STEPS = [-4.0 + 0.08 * step for step in range(101)]
_BELL = [(z, exp(-0.5 * z * z)) for z in _STEPS]
_BELL_SUM = sum(weight for _z, weight in _BELL)


def _key(context, receipts, *rest):
    return (id(context), tuple(str(e["order_id"]) for e in receipts)) + rest


def _settled(receipts):
    return [entry for entry in receipts if not entry.get("refusal")]


def _the_shift(context, receipts):
    # "the next shift the campaign runs that has no settled order against it"
    done = {str(entry["shift_id"]) for entry in _settled(receipts)}
    for shift in context["shifts"]:
        if str(shift) not in done:
            return str(shift)
    return str(context["shifts"][-1])


def _rows(context, key):
    # "`drops_fcst` is the number the engine put out ... Read `drops_fcst`."
    memo = _MEMO.setdefault((id(context), "rows", key), {})
    if not memo:
        for row in context[key]:
            memo.setdefault(str(row["as_of_shift"]), []).append(
                (str(row["zone_code"]), str(row["window"]), float(row["drops_fcst"]))
            )
    return memo


def _stamped(context, key, shift, back):
    # "its rows for a shift carry the stamp of the shift before it" — the step
    # back is one place on the shift calendar, not one day on the wall.
    days = [str(day) for day in context["calendar"]]
    position = days.index(str(shift)) - int(back)
    if position < 0:
        return []
    return _rows(context, key).get(days[position], [])


def _table(context, shift):
    # "in whichever area the routing table gives it for the shift you are
    # ordering. Take that from the routing table against the shift itself"
    cached = _MEMO.get((id(context), "table", str(shift)))
    if cached is None:
        cached = {}
        for row in context["routing_rows"]:
            start = str(row["effective_from"])
            end = str(row.get("effective_to") or "")
            if start > str(shift) or (end and end < str(shift)):
                continue
            zone = str(row["zone_code"])
            if zone not in cached or start > cached[zone][0]:
                cached[zone] = (start, str(row["area"]))
        cached = {zone: area for zone, (_start, area) in cached.items()}
        _MEMO[(id(context), "table", str(shift))] = cached
    return cached


AREAS = (("Harbour", "harbour_rows"), ("Ridge", "ridge_rows"))


def _cut(context, receipts):
    """Which engine stamps a row with the shift before it, off the settled week."""

    cached = _MEMO.get(_key(context, receipts, "cut"))
    if cached is not None:
        return cached
    chosen = {}
    for area, key in AREAS:
        scores = []
        for back in (0, 1):
            misses = []
            for entry in _settled(receipts):
                shift = str(entry["shift_id"])
                table = _table(context, shift)
                sheet = sum(
                    drops
                    for zone, _window, drops in _stamped(context, key, shift, back)
                    if table.get(zone) == area
                )
                meter = sum(
                    float(line["drops_metered"])
                    for line in entry["lines"]
                    if line["area"] == area and line.get("drops_metered") is not None
                )
                if sheet > 0 and meter > 0:
                    misses.append(abs(meter / sheet - 1.0))
            scores.append((sum(misses) / len(misses) if misses else 1e9, back))
        chosen[area] = min(scores)[1]
    _MEMO[_key(context, receipts, "cut")] = chosen
    return chosen


def _sheet(context, receipts, shift):
    """{(area, window): drops} for one shift, every zone counted once."""

    cached = _MEMO.get(_key(context, receipts, "sheet", str(shift)))
    if cached is not None:
        return cached
    back = _cut(context, receipts)
    table = _table(context, shift)
    seen = {}
    for area, key in AREAS:
        for zone, window, drops in _stamped(context, key, shift, back[area]):
            seen[(zone, window)] = drops
    totals = {
        (area, window): 0.0
        for area, _key in AREAS
        for window in context["windows"]
    }
    for (zone, window), drops in seen.items():
        target = (table.get(zone), window)
        if target in totals:
            totals[target] += drops
    _MEMO[_key(context, receipts, "sheet", str(shift))] = totals
    return totals


def _calendar_spread(context, receipts):
    """The spread of the promotion calendar's move over the settled shifts."""

    cached = _MEMO.get(_key(context, receipts, "spread"))
    if cached is not None:
        return cached
    moves = []
    for entry in _settled(receipts):
        shift = str(entry["shift_id"])
        sheet = sum(_sheet(context, receipts, shift).values())
        meter = sum(
            float(line["drops_metered"])
            for line in entry["lines"]
            if line.get("drops_metered") is not None
        )
        if sheet > 0 and meter > 0:
            moves.append(meter / sheet - 1.0)
    if len(moves) < 2:
        spread = 0.0
    else:
        mean = sum(moves) / len(moves)
        spread = sqrt(sum((move - mean) ** 2 for move in moves) / (len(moves) - 1))
    _MEMO[_key(context, receipts, "spread")] = spread
    return spread


def _band(context, receipts, drops):
    # "two of those spreads either side of it, low end first, and never tighter
    # than the meter's own five-drop rounding"
    spread = _calendar_spread(context, receipts)
    floor = float(context["desk"]["meter_rounds_to"]) / 2.0
    half = max(2.0 * spread * float(drops), floor)
    return [float(drops) - half, float(drops) + half]


def _short(context, receipts, drops, vans):
    """The vans a window is expected to run short of with `vans` on it."""

    rate = int(context["agreement"]["drops_per_van"])
    spread = _calendar_spread(context, receipts)
    step = float(context["desk"]["meter_rounds_to"])
    total = 0.0
    for z, weight in _BELL:
        turned_up = step * round(float(drops) * (1.0 + z * spread) / step)
        needed = -(-int(max(turned_up, 0)) // rate)
        if needed > vans:
            total += weight * (needed - vans)
    return total / _BELL_SUM


def analyze(context, receipts):
    shift = _the_shift(context, receipts)
    sheet = _sheet(context, receipts, shift)
    lines = []
    for area in context["areas"]:
        for window in context["windows"]:
            drops = sheet[(area, window)]
            lines.append(
                {
                    "area": area,
                    "window": window,
                    "drops": drops,
                    "drops_range": _band(context, receipts, drops),
                }
            )
    # "The zone rows are the number", so the pack's one network line is the
    # eight of them added up, and "the whole network's range on its single line
    # is two of those spreads either side of the network total ... not the eight
    # windows' ranges narrowed against one another", which is the same two
    # spreads the eight rows carry rather than a narrower combination of them.
    total = sum(sheet.values())
    return {
        "shift_id": shift,
        "demand": lines,
        "shift_total": {"drops": total, "drops_range": _band(context, receipts, total)},
        # "Every order this campaign has been charged for appears in the pack
        # once, with its order id, the shift it covers and the van-hours on it."
        "settlements": [
            {
                "order_id": entry["order_id"],
                "shift_id": entry["shift_id"],
                "van_hours_charged": entry["van_hours_charged"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    terms = context["agreement"]
    minimum = int(terms["minimum_booking_van_hours"])
    left = float(terms["allowance_van_hours"]) - sum(
        float(entry["van_hours_charged"]) for entry in receipts
    )
    # "When what is left will not carry the carrier's minimum there is nothing
    # to order, and the answer is a stop."
    if left < minimum:
        return "stop"
    shift = _the_shift(context, receipts)
    sheet = _sheet(context, receipts, shift)
    cap = int(terms["vans_per_area_window"])
    multiple = float(terms["spill_multiple"])
    # "Every area and window carries at least one van."
    vans = {key: 1 for key in sheet}
    spent = len(vans)

    def worth(key):
        held = vans[key]
        if held >= cap:
            return -1e9
        saved = _short(context, receipts, sheet[key], held) - _short(
            context, receipts, sheet[key], held + 1
        )
        return multiple * saved - 1.0

    while spent < left:
        pick = max(vans, key=worth)
        gain = worth(pick)
        if gain <= -1e8:
            break
        if gain <= 0 and spent >= minimum:
            break
        vans[pick] += 1
        spent += 1
    return {
        "booking": [
            {"area": area, "window": window, "vans": count}
            for (area, window), count in sorted(vans.items())
        ]
    }
'''
