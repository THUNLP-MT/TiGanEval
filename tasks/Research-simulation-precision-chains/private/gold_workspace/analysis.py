"""The quarter's readout: how often the fitted model puts a peak wait over 2.5 s.

The charter asks for a share of quarters, not for the middle of the draws, so
the readout counts the stored steps that put the quarter over the second and
divides by the steps it kept.

A run stores every step it took on the way down onto the surface, and those
steps read high; the proposal scale is still being moved while they are written,
so where each run's own block ends is on the file. One run was resubmitted from
another's stored state and the console replayed that run's remaining steps
before going on, so those rows stand in both files and belong to the readout
once.

Crossings arrive in bouts, so the draws say far less about the share than their
count suggests. The width is worked twice, once off how far agreement between
steps reaches and once off segments longer than a bout, and the wider is what
goes out.
"""

from support import (
    kept_blocks,
    published_width,
    settles_it,
    share,
    steps_kept,
    steps_left,
)


def analyze(context, receipts):
    blocks = kept_blocks(context)
    value = share(blocks)
    spread = published_width(blocks, value)
    return {
        "answer": round(value, 3),
        "answer_range": [value - spread, value + spread],
        "steps_kept": steps_kept(blocks),
        "steps_set_aside": sum(block["set_aside"] for block in blocks),
        "runs": [
            {
                "chain_id": block["chain_id"],
                "steps_stored": block["steps_stored"],
                "steps_kept": len(block["flags"]),
                "steps_set_aside": block["set_aside"],
            }
            for block in blocks
        ],
        "jobs": [
            {
                "call_id": entry["call_id"],
                "steps_charged": entry["steps_charged"],
                "refused": bool(entry.get("refusal")),
            }
            for entry in receipts
        ],
    }


def next_run(context, receipts):
    """Buy the steps that add crossings this quarter is short of.

    A run with a large proposal scale leaves its congested stretches quickly, so
    a step bought there is worth more than a step on a run that sits in them; the
    resubmitted run carries the scale of the run it was opened from and is the
    slowest of the set. Nothing is worth buying once the range already settles
    the commitment, or once the grant will not carry the smallest job the console
    will take.
    """

    budget = context["budget"]
    left = steps_left(context, receipts)
    minimum = int(budget["minimum_steps_per_job"])
    blocks = kept_blocks(context)
    value = share(blocks)
    spread = published_width(blocks, value)
    if left < minimum or settles_it(context, value - spread, value + spread):
        return "stop"
    steps = min(int(budget["cap_steps_per_job"]), left)
    picked = None
    for chain, block in zip(context["chains"], blocks):
        if "@" in str(chain.get("init_source") or ""):
            continue
        if picked is None or block["step_size"] > picked["step_size"]:
            picked = block
    if picked is None:
        return {"start": "new", "steps": steps}
    return {"chain_id": picked["chain_id"], "steps": steps}
