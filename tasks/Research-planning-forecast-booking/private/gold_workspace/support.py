"""Reading the desk's evidence: which rows are which shift, and what they cost.

The reporting stack calls the notebook once per campaign state, and the same
campaign comes round again for every state, so everything here that costs more
than a lookup is kept against the publication it was read from.
"""

from math import exp, sqrt


AREA_ROWS = (("Harbour", "harbour_rows"), ("Ridge", "ridge_rows"))

#: A standard normal on a fixed grid, so a window's chance of running short is
#: the same number every time it is asked for.
_STEPS = [-4.5 + 0.075 * step for step in range(121)]
_WEIGHTS = [exp(-0.5 * z * z) for z in _STEPS]
NORMAL = [(z, weight / sum(_WEIGHTS)) for z, weight in zip(_STEPS, _WEIGHTS)]

_MEMO = {}


def _keep(key, build):
    if key not in _MEMO:
        _MEMO[key] = build()
    return _MEMO[key]


def _ledger_key(receipts):
    return tuple(str(entry["order_id"]) for entry in receipts)


# -- the calendar ------------------------------------------------------------


def shifts(context):
    return list(context["shifts"])


def stamp_before(context, shift, places):
    """The stamp `places` places back along the desk's own shift calendar."""

    days = list(context["calendar"])
    index = days.index(str(shift)) - int(places)
    return days[index] if index >= 0 else None


def settled(receipts):
    return [entry for entry in receipts if not entry.get("refusal")]


def next_shift(context, receipts):
    done = {str(entry["shift_id"]) for entry in settled(receipts)}
    for shift in shifts(context):
        if shift not in done:
            return shift
    return shifts(context)[-1]


# -- which rows describe which shift ----------------------------------------


def rows_by_stamp(context, area_key):
    def build():
        found = {}
        for row in context[area_key]:
            found.setdefault(str(row["as_of_shift"]), {})[
                (str(row["zone_code"]), str(row["window"]))
            ] = float(row["drops_fcst"])
        return found

    return _keep((id(context), "rows", area_key), build)


def sheet_for(context, area_key, shift, places):
    """{(zone, window): drops} the area's engine published for one shift."""

    stamp = stamp_before(context, shift, places)
    if stamp is None:
        return {}
    return rows_by_stamp(context, area_key).get(stamp, {})


def routing(context):
    def build():
        table = {}
        for row in context["routing_rows"]:
            table.setdefault(str(row["zone_code"]), []).append(
                (
                    str(row["effective_from"]),
                    str(row.get("effective_to") or ""),
                    str(row["area"]),
                )
            )
        return table

    return _keep((id(context), "routing"), build)


def area_of(context, zone, shift):
    """The area answering for one zone on one shift, off the routing table."""

    def build():
        found = {}
        for code, spans in routing(context).items():
            best = None
            for start, end, area in spans:
                if start > str(shift) or (end and end < str(shift)):
                    continue
                if best is None or start > best[0]:
                    best = (start, area)
            if best is not None:
                found[code] = best[1]
        return found

    return _keep((id(context), "area", str(shift)), build).get(str(zone))


def metered_of(entry, area, window=None):
    total = 0.0
    for line in entry["lines"]:
        if line["area"] != area or line.get("drops_metered") is None:
            continue
        if window is not None and line["window"] != window:
            continue
        total += float(line["drops_metered"])
    return total


def cut_places(context, receipts):
    """For each area, how many shifts before the shift its engine stamps a row.

    Both engines publish the same columns and neither says which shift the
    stamp is. The settled shifts do: read each area's own metered drops against
    the sheet the two readings would give, and take the reading the whole
    settled week sits closest to.
    """

    def build():
        places = {}
        for area, key in AREA_ROWS:
            best = None
            for offset in (0, 1):
                misses = []
                for entry in settled(receipts):
                    shift = str(entry["shift_id"])
                    sheet = 0.0
                    for (zone, _window), value in sheet_for(context, key, shift, offset).items():
                        if area_of(context, zone, shift) == area:
                            sheet += value
                    metered = metered_of(entry, area)
                    if sheet > 0 and metered > 0:
                        misses.append(abs(metered / sheet - 1.0))
                score = sum(misses) / len(misses) if misses else float("inf")
                if best is None or score < best[0]:
                    best = (score, offset)
            places[area] = best[1]
        return places

    return _keep((id(context), "places", _ledger_key(receipts)), build)


def demand(context, receipts, shift):
    """{(area, window): drops} for one shift, every zone under one area only."""

    def build():
        totals = {
            (area, window): 0.0
            for area, _key in AREA_ROWS
            for window in context["windows"]
        }
        places = cut_places(context, receipts)
        seen = {}
        for area, key in AREA_ROWS:
            for (zone, window), value in sheet_for(context, key, shift, places[area]).items():
                seen[(zone, window)] = value
        for (zone, window), value in seen.items():
            area = area_of(context, zone, str(shift))
            if area is not None and (area, window) in totals:
                totals[(area, window)] += value
        return totals

    return _keep((id(context), "demand", _ledger_key(receipts), str(shift)), build)


# -- how far a fresh shift moves --------------------------------------------


def calendar_moves(context, receipts):
    """One reading per settled shift: the whole network over its own sheet.

    A zone's own miss is its own and washes out over the network. What is left
    when the two areas are put together is the promotion calendar's move, and it
    is the same move for every zone of both areas on that shift.
    """

    moves = []
    for entry in settled(receipts):
        shift = str(entry["shift_id"])
        sheet = sum(demand(context, receipts, shift).values())
        metered = sum(
            float(line["drops_metered"])
            for line in entry["lines"]
            if line.get("drops_metered") is not None
        )
        if sheet > 0 and metered > 0:
            moves.append(metered / sheet - 1.0)
    return moves


def calendar_spread(context, receipts):
    def build():
        moves = calendar_moves(context, receipts)
        if len(moves) < 2:
            return 0.0
        mean = sum(moves) / len(moves)
        return sqrt(sum((move - mean) ** 2 for move in moves) / (len(moves) - 1))

    return _keep((id(context), "spread", _ledger_key(receipts)), build)


def half_width(context, receipts, drops):
    """Two of the calendar's own spreads, never under the meter's rounding."""

    spread = calendar_spread(context, receipts)
    rounding = float(context["desk"]["meter_rounds_to"]) / 2.0
    return max(2.0 * spread * float(drops), rounding)


# -- what an order costs -----------------------------------------------------


def short_tail(context, receipts, sheet_drops):
    """`tail[v]`: the vans a window is expected to run short of with `v` booked."""

    def build():
        rate = int(context["agreement"]["drops_per_van"])
        spread = calendar_spread(context, receipts)
        step = float(context["desk"]["meter_rounds_to"])
        weight_of = {}
        for z, weight in NORMAL:
            drops = step * round(float(sheet_drops) * (1.0 + z * spread) / step)
            needed = -(-int(max(drops, 0)) // rate)
            weight_of[needed] = weight_of.get(needed, 0.0) + weight
        top = max(weight_of)
        tail = [0.0] * (top + 2)
        for vans in range(top - 1, -1, -1):
            tail[vans] = tail[vans + 1] + sum(
                weight for needed, weight in weight_of.items() if needed > vans
            )
        return tail

    return _keep(
        (id(context), "tail", _ledger_key(receipts), round(float(sheet_drops), 3)), build
    )


def short_vans(context, receipts, sheet_drops, vans):
    tail = short_tail(context, receipts, sheet_drops)
    index = max(int(vans), 0)
    return tail[index] if index < len(tail) else 0.0


def allowance_left(context, receipts):
    spent = sum(float(entry["van_hours_charged"]) for entry in receipts)
    return float(context["agreement"]["allowance_van_hours"]) - spent


def order(context, receipts):
    """The next shift's order, or an empty order when nothing can be booked.

    Every window carries a van because the carrier will not run one empty. After
    that a van costs one van-hour and saves the spill it prevents, so the next
    van goes wherever it prevents most, and the order stops growing when the
    allowance is gone or the next van would prevent less than it costs.
    """

    terms = context["agreement"]
    left = allowance_left(context, receipts)
    minimum = int(terms["minimum_booking_van_hours"])
    if left < minimum:
        return {}
    shift = next_shift(context, receipts)
    sheets = demand(context, receipts, shift)
    cap = int(terms["vans_per_area_window"])
    multiple = float(terms["spill_multiple"])
    booked = {key: 1 for key in sheets}
    spent = len(booked)

    def saving(key):
        vans = booked[key]
        if vans >= cap:
            return float("-inf")
        prevented = short_vans(context, receipts, sheets[key], vans) - short_vans(
            context, receipts, sheets[key], vans + 1
        )
        return multiple * prevented - 1.0

    while spent < left:
        best = max(booked, key=saving)
        gain = saving(best)
        if gain == float("-inf"):
            break
        if gain <= 0 and spent >= minimum:
            break
        booked[best] += 1
        spent += 1
    return booked


def settlement_lines(receipts):
    """One line per order the desk was charged for, in the order they settled."""

    return [
        {
            "order_id": entry["order_id"],
            "shift_id": entry["shift_id"],
            "van_hours_charged": entry["van_hours_charged"],
        }
        for entry in receipts
    ]
