'A second notebook, written from `full_information.md` and from nothing else.'

from __future__ import annotations


ANALYSIS = '''"""2027 Q1 reservation capacity readout, built from the submission contract.

The desk's commitment is a share of quarters, so the readout counts the stored
steps whose peak wait is over 2.5 seconds and divides by the steps it read.

Every run stores the rows it wrote coming down onto the surface and they read
high; the proposal scale is still moving over those rows and holds steady after
them, so each run's own block is on its own file. A run whose `init_source`
names another run and a stored step was put back on that run's checkpoint and
re-walked what it had already written, so the replayed rows belong to the
quarter once.

Crossings arrive in bouts of a hundred steps or so, so the width is worked off
segments of two or three hundred steps, and the wider of the two goes out. The
range is the one that holds nineteen times in twenty.
"""

from support import (
    blocks_of,
    charged_left,
    closes_the_question,
    crossing_share,
    read_steps,
    widest,
)


def analyze(context, receipts):
    blocks = blocks_of(context)
    value = crossing_share(blocks)
    edge = widest(blocks)
    return {
        "answer": round(value, 3),
        "answer_range": [value - edge, value + edge],
        "steps_kept": read_steps(blocks),
        "steps_set_aside": sum(item["dropped"] for item in blocks),
        "runs": [
            {
                "chain_id": item["chain_id"],
                "steps_stored": item["stored"],
                "steps_kept": len(item["flags"]),
                "steps_set_aside": item["dropped"],
            }
            for item in blocks
        ],
        "jobs": [
            {
                "call_id": entry["call_id"],
                "steps_charged": entry["steps_charged"],
                "refused": entry.get("refusal") is not None,
            }
            for entry in receipts
        ],
    }


def next_run(context, receipts):
    """The job that buys the most of what the quarter is short of.

    The question is closed when the range this readout published is inside the
    width the review asks for and sits on one side of the line, so the stop is
    taken off `analyze`'s own range rather than off any other reading of the same
    draws.
    """

    budget = context["budget"]
    smallest = int(budget["minimum_steps_per_job"])
    left = charged_left(context, receipts)
    blocks = blocks_of(context)
    value = crossing_share(blocks)
    edge = widest(blocks)
    if left < smallest or closes_the_question(context, value - edge, value + edge):
        return "stop"
    pick = None
    for item in blocks:
        if item["resubmitted"]:
            continue
        if pick is None or item["scale"] > pick["scale"]:
            pick = item
    steps = min(int(budget["cap_steps_per_job"]), left)
    if pick is None:
        return {"start": "new", "steps": steps}
    return {"chain_id": pick["chain_id"], "steps": steps}
'''


SUPPORT = '''"""Helpers for the contract build of the capacity readout."""

from math import sqrt

#: The charter's range is the one that holds nineteen times in twenty.
CONFIDENCE = 1.959963984540054
#: The submission asks for segments of two or three hundred steps, a few times
#: the length of a congested stretch. Both lengths are worked and the wider
#: answer is the one published.
SEGMENTS = (200, 300)


def _opening_block(scale):
    """How many rows a run wrote before its proposal scale stopped moving."""

    if not scale:
        return 0
    held = scale[-1]
    index = len(scale)
    while index > 0 and scale[index - 1] == held:
        index -= 1
    return index


def _replayed(chain, catalogue, start):
    """How many of this run's opening rows are another run's rows over again."""

    source = str(chain.get("init_source") or "")
    if "@" not in source:
        return 0
    name, _, position = source.split("@")[0], "@", source.split("@")[1]
    parent = catalogue.get(name)
    if parent is None:
        return 0
    try:
        offset = int(position)
    except ValueError:
        return 0
    mine = chain["draws"]
    theirs = parent["draws"]
    count = 0
    while start + count < len(mine["arrival_rate"]) and offset + count < len(theirs["arrival_rate"]):
        if (
            mine["arrival_rate"][start + count] != theirs["arrival_rate"][offset + count]
            or mine["service_rate"][start + count] != theirs["service_rate"][offset + count]
        ):
            break
        count += 1
    return count


def blocks_of(context):
    """Per run, the rows that belong in the readout and the rows that do not."""

    over = float(context["commitment"]["peak_wait_s"])
    catalogue = {item["chain_id"]: item for item in context["chains"]}
    out = []
    for chain in context["chains"]:
        draws = chain["draws"]
        opening = _opening_block(draws["step_size"])
        again = _replayed(chain, catalogue, opening)
        dropped = opening + again
        out.append(
            {
                "chain_id": chain["chain_id"],
                "stored": len(draws["peak_wait_s"]),
                "dropped": dropped,
                "resubmitted": again > 0,
                "scale": draws["step_size"][0] if draws["step_size"] else 0.0,
                "flags": [1 if value > over else 0 for value in draws["peak_wait_s"][dropped:]],
            }
        )
    return out


def read_steps(blocks):
    return sum(len(item["flags"]) for item in blocks)


def crossing_share(blocks):
    steps = read_steps(blocks)
    if not steps:
        return 0.0
    return sum(sum(item["flags"]) for item in blocks) / steps


def _segment_edge(blocks, length):
    parts = []
    for item in blocks:
        flags = item["flags"]
        cut = len(flags) // length
        for index in range(cut):
            piece = flags[index * length : (index + 1) * length]
            parts.append(sum(piece) / length)
    if len(parts) < 3:
        return None
    centre = sum(parts) / len(parts)
    spread = sum((part - centre) ** 2 for part in parts) / (len(parts) - 1)
    return CONFIDENCE * sqrt(spread / len(parts))


def widest(blocks):
    """The wider of the two segment lengths, which is what goes out."""

    edges = [edge for edge in (_segment_edge(blocks, size) for size in SEGMENTS) if edge]
    if not edges:
        return 0.5
    return max(edges)


def charged_left(context, receipts):
    budget = context["budget"]
    spent = sum(int(entry["steps_charged"]) for entry in receipts)
    return int(budget["steps_granted"]) - int(budget["steps_spent_before_receipts"]) - spent


def closes_the_question(context, low, high):
    commitment = context["commitment"]
    line = float(commitment["quarters_over_share"])
    if high - low > float(commitment["range_width_wanted"]) + 1e-12:
        return False
    return low >= line or high <= line
'''


FILES = {"analysis.py": ANALYSIS, "support.py": SUPPORT}
