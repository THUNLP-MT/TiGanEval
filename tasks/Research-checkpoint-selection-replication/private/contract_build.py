'Two readouts as somebody who had only read `full_information.md` would write them.'

CONTRACT_BUILD = '''"""Release readout, written off the board's terms."""

POINT = 0.01
SHORTLIST = 4


def _ran(ledger):
    return [
        entry
        for entry in ledger
        if not entry.get("refusal") and str(entry.get("kind", "reads")) == "reads"
    ]


def _scores(entry, item):
    return [
        float(row["val_score"])
        for row in entry.get("rows", ())
        if str(row["item"]) == str(item)
    ]


def paired(ledger, model):
    """Differences taken inside one job, in points, per checkpoint.

    "The desk scores every item in a job on the same passes of the lot the job
    names, so a difference taken inside one job has the lot and the pass out of
    it at both ends."
    """

    out = {}
    for entry in _ran(ledger):
        against = _scores(entry, model)
        if not against:
            continue
        seen = []
        for row in entry.get("rows", ()):
            name = str(row["item"])
            if name != str(model) and name not in seen:
                seen.append(name)
        for name in seen:
            mine = _scores(entry, name)
            for index in range(min(len(mine), len(against))):
                out.setdefault(name, []).append((mine[index] - against[index]) / POINT)
    return out


def _mean(values):
    return sum(values) / len(values)


def _standard_error(values):
    """Two standard errors of the mean of the differences themselves."""

    if len(values) < 2:
        return None
    middle = _mean(values)
    variance = sum((value - middle) ** 2 for value in values) / (len(values) - 1)
    return 2.0 * (variance / len(values)) ** 0.5


def _lot_move(context):
    """Twice the move between lots, for a reading that never paired the two."""

    levels = {}
    for row in context["run_ledger"]:
        levels.setdefault(str(row["val_lot"]), []).append(float(row["val_score"]))
    means = [_mean(values) for values in levels.values()]
    if len(means) > 1:
        return 2.0 * (max(means) - min(means)) / POINT
    return 2.0 * max((max(v) - min(v)) / 2.0 for v in levels.values()) / POINT


def _step(item):
    return int(str(item).split("@")[1])


def choose(held):
    """The row the readout names.

    "A row read three times and a row read eight times are not on the same
    footing, so the row the readout names is the one the lot was actually spent
    on — the row with the most paired reads — and where two rows read the same
    number of times sit inside each other's range the earlier checkpoint is the
    one to ship."
    """

    deepest = max(len(values) for values in held.values())
    best = [name for name in held if len(held[name]) == deepest]
    leader = max(best, key=lambda name: _mean(held[name]))
    width = _standard_error(held[leader]) or 0.0
    tied = [
        name
        for name in best
        if _mean(held[leader]) - _mean(held[name]) <= width
    ]
    return min(tied, key=lambda name: (_step(name), name))


def on_disk(context):
    return [
        str(row["checkpoint_id"])
        for row in context["checkpoint_registry"]
        if str(row["on_disk"]).lower() == "yes"
    ]


def shortlist(context):
    kept = set(on_disk(context))
    rows = [
        row
        for row in context["run_ledger"]
        if "{0}@{1}".format(row["run_id"], row["checkpoint_step"]) in kept
    ]
    rows.sort(key=lambda row: -float(row["val_score"]))
    return [
        "{0}@{1}".format(row["run_id"], row["checkpoint_step"]) for row in rows[:SHORTLIST]
    ]


def spent(ledger):
    return sum(int(entry["units_charged"]) for entry in ledger)


def free_units(context, ledger):
    grant = int(context["compute"]["units_granted"])
    return grant - spent(ledger) - int(context["compute"]["reserved_units"])


def passes_used(ledger, lot):
    return sum(
        int(entry.get("repeats") or 0)
        for entry in _ran(ledger)
        if str(entry.get("lot")) == str(lot)
    )


def analyze(context, ledger):
    model = str(context["release"]["model_id"])
    held = paired(ledger, model)
    if held:
        shipped = choose(held)
        gain = _mean(held[shipped])
        half = _standard_error(held[shipped])
        if half is None:
            half = _lot_move(context)
        window = [gain - half, gain + half]
    else:
        kept = shortlist(context)
        shipped = kept[0] if kept else None
        gain = None
        window = None
    return {
        "shipped_checkpoint": shipped,
        "gain_points": gain,
        "gain_range": window,
        "jobs": [
            {
                "job_id": entry["job_id"],
                "lot": entry.get("lot"),
                "reads": int(entry.get("reads_returned") or 0),
                "units_charged": int(entry["units_charged"]),
            }
            for entry in ledger
        ],
        "units_left": int(context["compute"]["units_granted"]) - spent(ledger),
    }


def next_collection(context, ledger):
    model = str(context["release"]["model_id"])
    price = int(context["compute"]["price_per_read"])
    cap = int(context["compute"]["job_cap_units"])
    passes = int(context["lots"]["reads_per_lot"])
    held = paired(ledger, model)

    if held:
        leader = choose(held)
        lots = [
            str(entry.get("lot"))
            for entry in _ran(ledger)
            if _scores(entry, leader) and _scores(entry, model)
        ]
        lot = max(sorted(set(lots)), key=lots.count)
        half = _standard_error(held[leader])
        read_out = passes_used(ledger, lot) >= passes
        if (
            read_out
            and half is not None
            and 2.0 * half <= float(context["review"]["range_ask_points"])
        ):
            return "stop"
        items = [leader, model]
        wanted = None
    else:
        items = shortlist(context) + [model]
        lot = min(
            context["lots"]["open"], key=lambda name: (passes_used(ledger, name), name)
        )
        wanted = 3

    while items:
        room = min(
            passes - passes_used(ledger, lot),
            free_units(context, ledger) // (price * len(items)),
            cap // (price * len(items)),
        )
        if wanted is not None:
            room = min(room, wanted)
        if room >= 1:
            return {"kind": "reads", "lot": lot, "items": items, "repeats": int(room)}
        if len(items) <= 2:
            return "stop"
        items = [items[0], items[-1]]
    return "stop"
'''

LOT_OF_RECORD_SUPPORT = '''"""Reading a campaign the way the release tooling publishes it.

Everything here works off the tables the tooling hands the notebook and off the
evaluation desk's own receipt stream. Nothing is written for one campaign.
"""

from math import isfinite, sqrt


POINT = 100.0  # one point of val_score is 0.01


def number(value):
    """One figure, from a JSON number or a decimal string; None when unreadable."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if isfinite(float(value)) else None
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def whole(value, default=0):
    read = number(value)
    return int(round(read)) if read is not None else default


def checkpoint_id(row):
    return "{}@{}".format(row.get("run_id"), whole(row.get("checkpoint_step")))


def step_of(item):
    text = str(item)
    if "@" in text:
        tail = text.rsplit("@", 1)[1]
        try:
            return int(tail)
        except ValueError:
            return None
    return None


def on_disk(context):
    """The checkpoint ids the registry still shows on disk."""

    kept = set()
    for row in context.get("checkpoint_registry") or ():
        flag = row.get("on_disk")
        if isinstance(flag, str):
            live = flag.strip().lower() in ("yes", "true", "y", "1")
        else:
            live = bool(flag)
        if live:
            kept.add(str(row.get("checkpoint_id") or checkpoint_id(row)))
    return kept


def turn_steps(context, rise=0.02):
    """Per run, the step its own held-back loss stops improving at.

    "Two runs were on the long warm-up and turn down after their turn step ...
    and their own curves under curves/ show it while the ledger rows do not say
    so." A run whose curve only wanders at the end has no turn.
    """

    turns = {}
    for run_id, curve in (context.get("curves") or {}).items():
        points = []
        for row in curve:
            step = whole(row.get("step"), -1)
            loss = number(row.get("holdout_loss"))
            if step >= 0 and loss is not None:
                points.append((step, loss))
        if not points:
            continue
        points.sort()
        best_step, best_loss = min(points, key=lambda item: item[1])
        after = [loss for step, loss in points if step > best_step]
        if after and max(after) - best_loss > rise:
            turns[str(run_id)] = best_step
    return turns


def lot_levels(context):
    """What the table reads at on each lot, in points.

    "Each lot has a level of its own, and the two this campaign ran on sit
    further apart than anything that separates the checkpoints we are choosing
    between." The column mean is the only reading of that level the table has.
    """

    totals = {}
    for row in context.get("run_ledger") or ():
        score = number(row.get("val_score"))
        if score is None:
            continue
        lot = str(row.get("val_lot"))
        count, total = totals.get(lot, (0, 0.0))
        totals[lot] = (count + 1, total + score)
    return {lot: (total / count) * POINT for lot, (count, total) in totals.items() if count}


def lot_move(context):
    """The widest distance between two lots' levels, in points."""

    levels = sorted(lot_levels(context).values())
    return (levels[-1] - levels[0]) if len(levels) > 1 else 0.0


def table_candidates(context):
    """Table rows worth reading again, best first.

    Rows are compared after their own lot level is taken off. Rows the retention
    job cleared cannot be scored again, and rows a run wrote after its own curve
    turned are worse than that run's own earlier ones however high they sit.
    """

    kept = on_disk(context)
    turns = turn_steps(context)
    levels = lot_levels(context)
    rows = []
    for row in context.get("run_ledger") or ():
        score = number(row.get("val_score"))
        if score is None:
            continue
        item = checkpoint_id(row)
        if item not in kept:
            continue
        run_id = str(row.get("run_id"))
        step = whole(row.get("checkpoint_step"))
        if run_id in turns and step > turns[run_id]:
            continue
        lot = str(row.get("val_lot"))
        rows.append(
            {
                "item": item,
                "run_id": run_id,
                "step": step,
                "lot": lot,
                "score_points": score * POINT,
                "adjusted": score * POINT - levels.get(lot, 0.0),
            }
        )
    rows.sort(key=lambda entry: (-entry["adjusted"], entry["step"], entry["item"]))
    seen, unique = set(), []
    for entry in rows:
        if entry["item"] in seen:
            continue
        seen.add(entry["item"])
        unique.append(entry)
    return unique


def receipts(ledger):
    return [entry for entry in (ledger or ()) if isinstance(entry, dict)]


def job_lines(ledger):
    """One line per job the stream carries, refused ones included, in order."""

    lines, seen = [], set()
    for entry in receipts(ledger):
        job_id = entry.get("job_id")
        if job_id in seen:
            continue
        seen.add(job_id)
        lines.append(
            {
                "job_id": job_id,
                "lot": entry.get("lot"),
                "reads": whole(entry.get("reads_returned")),
                "units_charged": whole(entry.get("units_charged")),
            }
        )
    return lines


def units_charged(ledger):
    return sum(line["units_charged"] for line in job_lines(ledger))


def units_left(context, ledger):
    granted = whole((context.get("compute") or {}).get("units_granted"))
    return granted - units_charged(ledger)


def free_units(context, ledger):
    """What the campaign may spend: the grant less the reserve and what is gone."""

    reserve = whole((context.get("compute") or {}).get("reserved_units"))
    return units_left(context, ledger) - reserve


def slices_served(ledger):
    """Per lot, how many passes of it the desk has already served."""

    served = {}
    for entry in receipts(ledger):
        lot = str(entry.get("lot"))
        for row in entry.get("rows") or ():
            slice_no = whole(row.get("slice_no"), 0)
            if slice_no > served.get(lot, 0):
                served[lot] = slice_no
    return served


def slices_left(context, ledger, lot):
    total = whole((context.get("lots") or {}).get("reads_per_lot"))
    return max(0, total - slices_served(ledger).get(str(lot), 0))


def paired_differences(context, ledger):
    """(lot, item) -> the differences against the released model, in points.

    "The desk scores every item in a job on the same passes of the lot the job
    names, so a difference taken inside one job has the lot and the pass out of
    it at both ends." Reads from two different jobs are not paired.
    """

    model = str((context.get("release") or {}).get("model_id"))
    paired = {}
    for entry in receipts(ledger):
        if entry.get("refusal"):
            continue
        lot = str(entry.get("lot"))
        by_slice = {}
        for row in entry.get("rows") or ():
            score = number(row.get("val_score"))
            if score is None:
                continue
            by_slice.setdefault(whole(row.get("slice_no"), 0), {})[str(row.get("item"))] = score
        for reads in by_slice.values():
            if model not in reads:
                continue
            for item, score in reads.items():
                if item == model:
                    continue
                paired.setdefault((lot, item), []).append((score - reads[model]) * POINT)
    return paired


def mean(values):
    return sum(values) / len(values) if values else None


def spread_interval(values, sigmas=2.0):
    """The mean of the paired differences and two standard errors either side.

    "The range is two standard errors of the mean of those paired differences,
    worked off the spread of the differences themselves." One difference on its
    own says nothing about that spread.
    """

    count = len(values)
    centre = mean(values)
    if centre is None:
        return None
    if count < 2:
        return {"mean": centre, "half_width": None, "reads": count}
    variance = sum((value - centre) ** 2 for value in values) / (count - 1)
    half = sigmas * sqrt(variance) / sqrt(count)
    return {"mean": centre, "half_width": half, "reads": count}
'''


LOT_OF_RECORD_ANALYSIS = '''"""Release readout, answered on the lot the campaign has read most of.

The number the board takes is one checkpoint against the model in production,
read on one lot inside one desk job, so that the lot and the pass the reads sat
on come out of both ends of the difference. `analyze` reports the checkpoint,
the mean of the paired differences behind it, two standard errors of that mean
either side, a line for every job the receipt stream carries and what the grant
has left. `next_collection` asks the desk for the reads that would narrow it,
inside the grant, the reserve, the job cap and the passes of the lot the desk
has not sold yet.
"""

from support import (
    POINT,
    free_units,
    job_lines,
    lot_move,
    number,
    paired_differences,
    slices_left,
    spread_interval,
    step_of,
    table_candidates,
    units_left,
    whole,
)


SHORTLIST_READS = 3          # "Three reads apiece is enough to put a shortlist in order"
MAX_SHORTLIST = 6            # beyond this a shortlist stops being one


def _readings(context, ledger):
    """(lot, item) -> mean, half width and read count, from the paired reads."""

    return {
        key: spread_interval(values)
        for key, values in paired_differences(context, ledger).items()
    }


def _lot_of_record(readings):
    """The lot the number is taken on: the one the campaign has read most of."""

    weight = {}
    for (lot, _item), reading in readings.items():
        weight[lot] = weight.get(lot, 0) + reading["reads"]
    if not weight:
        return None
    return sorted(weight.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _bounds(reading):
    half = reading["half_width"]
    if half is None:
        return None
    return reading["mean"] - half, reading["mean"] + half


def _each_inside_the_other(one, other):
    """Two readings sit inside each other's range: they are the same reading.

    A row read three times carries a range several times as wide as a row read
    eight times does, so its range holding the other one is not the two of them
    sitting inside each other.
    """

    first, second = _bounds(one), _bounds(other)
    if first is None or second is None:
        return False
    return (
        first[0] >= second[0]
        and first[1] <= second[1]
        and second[0] >= first[0]
        and second[1] <= first[1]
    )


def _shipped(readings, lot, ask=None):
    """The checkpoint to ship, from the rows the lot was actually spent on.

    "A row read three times and a row read eight times are not on the same
    footing, so the row the readout names is the one the lot was actually spent
    on — the row with the most paired reads — and where two rows read the same
    number of times sit inside each other's range the earlier checkpoint is the
    one to ship."
    """

    on_lot = {item: reading for (this, item), reading in readings.items() if this == lot}
    if not on_lot:
        return None
    promotable = {
        item: reading
        for item, reading in on_lot.items()
        if reading["half_width"] is not None
        and reading["mean"] - reading["half_width"] > 0.0
        and (ask is None or 2.0 * reading["half_width"] <= ask)
    }
    if promotable:
        on_lot = promotable
    leader = max(
        on_lot,
        key=lambda item: (
            on_lot[item]["reads"],
            on_lot[item]["mean"],
            -(step_of(item) or 0),
        ),
    )
    tied = [
        item
        for item, reading in on_lot.items()
        if item == leader or _each_inside_the_other(reading, on_lot[leader])
    ]
    return min(tied, key=lambda item: (step_of(item) if step_of(item) is not None else 0, item))


def analyze(context, ledger):
    readings = _readings(context, ledger)
    lot = _lot_of_record(readings)
    ask = number((context.get("review") or {}).get("range_ask_points"))
    shipped = _shipped(readings, lot, ask) if lot else None

    if shipped is not None:
        reading = readings[(lot, shipped)]
        gain = reading["mean"]
        half = reading["half_width"]
        if half is None:
            # One read is a reading with no spread behind it; the move between
            # two lots is the smallest honest width there is.
            half = 2.0 * lot_move(context)
    else:
        # Nothing on the stream puts a checkpoint and the model on one lot
        # together. The only reading left crosses from the lot a row sat on to
        # the lot the stored figure was read on, so "the move between lots is in
        # it at both ends, and the range has to carry that move twice over".
        candidates = table_candidates(context)
        if not candidates:
            return {
                "shipped_checkpoint": None,
                "gain_points": None,
                "gain_range": None,
                "jobs": job_lines(ledger),
                "units_left": units_left(context, ledger),
            }
        best = candidates[0]
        shipped = best["item"]
        stored = number((context.get("release") or {}).get("stored_val_score"))
        gain = best["score_points"] - (stored * POINT if stored is not None else 0.0)
        half = 2.0 * lot_move(context)

    return {
        "shipped_checkpoint": shipped,
        "gain_points": gain,
        "gain_range": [gain - half, gain + half],
        "jobs": job_lines(ledger),
        "units_left": units_left(context, ledger),
    }


def _reads_job(lot, items, repeats):
    return {"kind": "reads", "lot": lot, "items": list(items), "repeats": int(repeats)}


def _affordable_repeats(free, cap, price, items, passes_left):
    per_pass = price * len(items)
    if per_pass <= 0:
        return 0
    return max(0, min(passes_left, free // per_pass, cap // per_pass))


def next_collection(context, ledger):
    compute = context.get("compute") or {}
    lots = context.get("lots") or {}
    review = context.get("review") or {}
    model = str((context.get("release") or {}).get("model_id"))
    price = whole(compute.get("price_per_read"), 0)
    cap = whole(compute.get("job_cap_units"), 0)
    free = free_units(context, ledger)
    if price <= 0 or free < 2 * price or cap < 2 * price:
        return "stop"

    readings = _readings(context, ledger)
    lot = _lot_of_record(readings)
    open_lots = [str(name) for name in (lots.get("open") or ())]

    if lot is not None:
        ask = number(review.get("range_ask_points"))
        shipped = _shipped(readings, lot, ask)
        reading = readings[(lot, shipped)]
        half = reading["half_width"]
        left_here = slices_left(context, ledger, lot)
        if left_here == 0 and half is not None and ask is not None and 2 * half <= ask:
            return "stop"
        # "The number itself wants the rest of that lot spent on the row that
        # came out ahead, because what is left inside a job is each item's own
        # luck on the rows it happened to get."
        for target in [lot] + [name for name in open_lots if name != lot]:
            passes_left = slices_left(context, ledger, target)
            repeats = _affordable_repeats(free, cap, price, [shipped, model], passes_left)
            if repeats >= 1:
                return _reads_job(target, [shipped, model], repeats)
        return "stop"

    # Nothing has been read yet: put a shortlist and the model on one lot, three
    # reads apiece, keeping back what the rest of that lot will cost on the row
    # that comes out ahead.
    candidates = [entry["item"] for entry in table_candidates(context)]
    if not candidates:
        return "stop"
    for target in sorted(open_lots, key=lambda name: -slices_left(context, ledger, name)):
        passes_left = slices_left(context, ledger, target)
        if passes_left < 1:
            continue
        reads = min(SHORTLIST_READS, passes_left)
        rest = max(0, passes_left - reads) * 2 * price
        for size in range(min(MAX_SHORTLIST, len(candidates)), 0, -1):
            cost = (size + 1) * reads * price
            if cost <= cap and cost + rest <= free:
                return _reads_job(target, candidates[:size] + [model], reads)
        repeats = _affordable_repeats(free, cap, price, [candidates[0], model], passes_left)
        if repeats >= 1:
            return _reads_job(target, [candidates[0], model], repeats)
    return "stop"
'''


CONTRACT_BUILDS = (
    (
        "the rows the lot was spent on, pooled over the jobs",
        {"analysis.py": CONTRACT_BUILD, "support.py": ""},
    ),
    (
        "the lot of record, every read row ranked",
        {"analysis.py": LOT_OF_RECORD_ANALYSIS, "support.py": LOT_OF_RECORD_SUPPORT},
    ),
)
