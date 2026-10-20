"""Helpers for the capacity quarter's notebook."""

from math import sqrt

Z = 1.959963984540054


def crossing_flags(chain, threshold):
    """One flag per stored step of a run: did that step put the quarter over."""

    return [1 if value > threshold else 0 for value in chain["draws"]["peak_wait_s"]]


def settled_from(chain):
    """The first stored step of a run that is on the surface it is exploring.

    A run comes down onto the surface over its own number of steps, and the
    proposal scale is still being moved while it does. Once the scale stops
    moving the run is where it belongs, so the last step at which the scale
    changed is the first one worth reading. A run that opened at another run's
    stored state carries that run's scale from its very first row and has no
    such block.
    """

    scale = chain["draws"]["step_size"]
    last = 0
    for index in range(1, len(scale)):
        if scale[index] != scale[index - 1]:
            last = index
    return last


def replayed_from(chain, by_id, start):
    """How many of this run's opening steps are another run's steps over again.

    `init_source` names the run and the stored step the console opened this one
    at. Everything the console replayed from there stands in both files step for
    step, and counting it twice counts a stretch of the same chain twice.
    """

    source = str(chain.get("init_source") or "")
    if "@" not in source:
        return 0
    name, _, at = source.partition("@")
    parent = by_id.get(name)
    if parent is None or not at.isdigit():
        return 0
    offset = int(at)
    mine = chain["draws"]
    theirs = parent["draws"]
    count = 0
    while (
        start + count < len(mine["peak_wait_s"])
        and offset + count < len(theirs["peak_wait_s"])
        and mine["peak_wait_s"][start + count] == theirs["peak_wait_s"][offset + count]
        and mine["accepted"][start + count] == theirs["accepted"][offset + count]
    ):
        count += 1
    return count


def kept_blocks(context):
    """Per run: the flags it contributes, how many steps it keeps and drops."""

    threshold = float(context["commitment"]["peak_wait_s"])
    by_id = {item["chain_id"]: item for item in context["chains"]}
    blocks = []
    for chain in context["chains"]:
        flags = crossing_flags(chain, threshold)
        settle = settled_from(chain)
        replayed = replayed_from(chain, by_id, settle)
        blocks.append(
            {
                "chain_id": chain["chain_id"],
                "step_size": chain["draws"]["step_size"][-1] if chain["draws"]["step_size"] else 0.0,
                "steps_stored": len(flags),
                "set_aside": settle + replayed,
                "flags": flags[settle + replayed :],
            }
        )
    return blocks


def share(blocks):
    kept = sum(len(block["flags"]) for block in blocks)
    crossings = sum(sum(block["flags"]) for block in blocks)
    return (crossings / kept) if kept else 0.0


def steps_kept(blocks):
    return sum(len(block["flags"]) for block in blocks)


def _lag_counts(flags, limit):
    """How many pairs of crossings sit each distance apart inside one run."""

    positions = [index for index, flag in enumerate(flags) if flag]
    counts = [0] * (limit + 1)
    size = len(positions)
    for first in range(size):
        start = positions[first]
        for second in range(first + 1, size):
            gap = positions[second] - start
            if gap > limit:
                break
            counts[gap] += 1
    return counts


def turnover(blocks, value, limit=400):
    """How many stored steps carry one step's worth of news about crossings.

    Crossings arrive in bouts, so two steps a little way apart say much the same
    thing. The run of agreement between steps that far apart is summed until it
    stops being positive, and that sum says how many steps one independent step
    is worth.
    """

    kept = steps_kept(blocks)
    if kept < 4 or value <= 0.0 or value >= 1.0:
        return 1.0
    limit = max(1, min(int(limit), kept // 4))
    totals = [0] * (limit + 1)
    pairs = [0] * (limit + 1)
    for block in blocks:
        flags = block["flags"]
        counts = _lag_counts(flags, limit)
        for gap in range(1, limit + 1):
            totals[gap] += counts[gap]
            pairs[gap] += max(0, len(flags) - gap)
    spread = value * (1.0 - value)
    total = 1.0
    gap = 1
    while gap < limit:
        first = (totals[gap] / pairs[gap] - value * value) / spread if pairs[gap] else 0.0
        second = (
            (totals[gap + 1] / pairs[gap + 1] - value * value) / spread
            if pairs[gap + 1]
            else 0.0
        )
        if first + second <= 0.0:
            break
        total += 2.0 * (first + second)
        gap += 2
    return max(1.0, total)


def width_from_turnover(blocks, value, steps):
    return Z * sqrt(value * (1.0 - value) * turnover(blocks, value) / steps)


def width_from_segments(blocks, value, length):
    """The width off segments of the runs, each long against a bout of crossings."""

    rates = []
    for block in blocks:
        flags = block["flags"]
        for start in range(0, len(flags) - length + 1, length):
            piece = flags[start : start + length]
            rates.append(sum(piece) / length)
    if len(rates) < 4:
        return 0.0
    middle = sum(rates) / len(rates)
    spread = sum((rate - middle) ** 2 for rate in rates) / (len(rates) - 1)
    return Z * sqrt(spread / len(rates))


def published_width(blocks, value):
    """The wider of the two ways of working it."""

    steps = steps_kept(blocks)
    if steps < 4:
        return 0.5
    first = width_from_turnover(blocks, value, steps)
    length = max(50, min(steps // 8, int(round(4.0 * turnover(blocks, value)))))
    second = width_from_segments(blocks, value, length)
    return max(first, second)


def steps_left(context, receipts):
    budget = context["budget"]
    return (
        int(budget["steps_granted"])
        - int(budget["steps_spent_before_receipts"])
        - sum(int(entry["steps_charged"]) for entry in receipts)
    )


def settles_it(context, low, high):
    """Whether a range that wide, sitting there, closes the quarter's commitment."""

    commitment = context["commitment"]
    wanted = float(commitment["range_width_wanted"])
    share_line = float(commitment["quarters_over_share"])
    return (high - low) <= wanted + 1e-12 and (low >= share_line or high <= share_line)
