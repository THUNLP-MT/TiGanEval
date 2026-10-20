"What the world says, computed from the model's own parameters and counts."

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from . import world as w


TOLERANCE = 0.010


CLASSIFY_SLACK = 0.004


NARROW_FACTOR = 0.55
WIDE_FACTOR = 1.70


COVERAGE = 0.9


CARRIED_OVER_GAP = 0.020


INVARIANCE_SLACK = 0.008

_Z = 1.959963984540054


def kept_counts(world: w.World) -> list[tuple[str, int, int, float]]:
    'Per run: how many stored steps belong in the reading, and what they say.'

    rows: list[tuple[str, int, int, float]] = []
    for chain in world.chains:
        keep = chain.crossing[chain.kept_from :]
        rows.append(
            (
                chain.chain_id,
                int(keep.size),
                int(keep.sum()),
                w.crossing_time(world.spec, chain.busy_run),
            )
        )
    return rows


def steps_kept(world: w.World) -> int:
    return int(sum(kept for _id, kept, _cross, _time in kept_counts(world)))


def truth(world: w.World) -> float:
    "The share of quarters the fitted model puts over the commitment's second."

    return w.truth(world.spec)


def reading(world: w.World) -> float:
    'What the draws this quarter kept give for that share.'

    rows = kept_counts(world)
    kept = sum(item[1] for item in rows)
    crossings = sum(item[2] for item in rows)
    return crossings / kept if kept else 0.0


def crossing_time(world: w.World) -> float:
    "How many stored steps carry one step's worth of news about crossings."

    rows = kept_counts(world)
    kept = sum(item[1] for item in rows)
    if not kept:
        return 1.0
    return sum(item[1] * item[3] for item in rows) / kept


def supported(world: w.World, kept: float) -> float:
    'Half the range that many kept draws of this quarter support.'

    if kept <= 0:
        return float("inf")
    value = truth(world)
    return _Z * math.sqrt(value * (1.0 - value) * crossing_time(world) / float(kept))


def half_width(world: w.World) -> float:
    return supported(world, steps_kept(world))


def interval(world: w.World) -> tuple[float, float]:
    value = reading(world)
    spread = half_width(world)
    return value - spread, value + spread


def settled(world: w.World, low: float, high: float) -> bool:
    'Whether a range that wide, sitting there, closes the commitment.'

    wanted = float(world.spec["range_width_wanted"])
    share = float(world.spec["commitment_share"])
    return (high - low) <= wanted + 1e-12 and (low >= share or high <= share)


def question_settled(world: w.World) -> bool:
    low, high = interval(world)
    return settled(world, low, high)


def _pooled(world: w.World, *, keep_settling: bool, keep_replay: bool) -> float:
    kept = crossings = 0
    for chain in world.chains:
        settle = int(chain.settle)
        replayed = int(chain.replayed)
        blocks = [chain.crossing[settle + replayed :]]
        if keep_settling and settle:
            blocks.append(chain.crossing[:settle])
        if keep_replay and replayed:
            blocks.append(chain.crossing[settle : settle + replayed])
        for block in blocks:
            kept += int(block.size)
            crossings += int(block.sum())
    return crossings / kept if kept else 0.0


def settling_retained(world: w.World) -> float:
    return _pooled(world, keep_settling=True, keep_replay=False)


def lineage_counted_twice(world: w.World) -> float:
    return _pooled(world, keep_settling=False, keep_replay=True)


def everything_pooled(world: w.World) -> float:
    return _pooled(world, keep_settling=True, keep_replay=True)


def middle_of_the_draws(world: w.World) -> float:
    "The mean of every stored peak wait, in seconds: the owner's own number."

    total = 0.0
    rows = 0
    for chain in world.chains:
        total += float(chain.peak.sum())
        rows += int(chain.peak.size)
    return total / rows if rows else 0.0


def misreadings(world: w.World) -> dict[str, float]:
    return {
        "settling_retained": settling_retained(world),
        "lineage_counted_twice": lineage_counted_twice(world),
        "everything_pooled": everything_pooled(world),
        "middle_of_the_draws": middle_of_the_draws(world),
    }


def _state(world: w.World) -> list[tuple[int, float]]:
    return [(kept, time) for _id, kept, _cross, time in kept_counts(world)]


def _half_from(world: w.World, state: Sequence[tuple[int, float]]) -> float:
    kept = sum(item[0] for item in state)
    if kept <= 0:
        return float("inf")
    value = truth(world)
    weighted = sum(item[0] * item[1] for item in state)
    return _Z * math.sqrt(value * (1.0 - value) * weighted) / kept


def half_width_after(world: w.World, chain_id: str | None, steps: int) -> float:
    'The range this quarter would support after one more job.'

    state = _state(world)
    if chain_id is None:
        template = world.spec["new_chain"]
        kept = max(0, int(steps) - int(template["settle"]))
        state.append((kept, w.crossing_time(world.spec, int(template["busy_run"]))))
    else:
        chain = world.chain(str(chain_id))
        if chain is None:
            return float("inf")
        state = [
            (kept + int(steps), time) if world.chains[index].chain_id == chain_id else (kept, time)
            for index, (kept, time) in enumerate(state)
        ]
    return _half_from(world, state)


def informativeness_bar(world: w.World, steps_left: int) -> float:
    'A fresh run of everything one job may carry, and no more.'

    size = min(int(world.spec["cap_steps"]), int(steps_left))
    return half_width_after(world, None, size)


def is_continuation(world: w.World, chain_id: str) -> bool:
    chain = world.chain(str(chain_id))
    return chain is not None and chain.parent is not None


def plan_state(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'What this quarter can still buy, and whether stopping is the only answer.'

    left = int(world.steps_left(receipts))
    minimum = int(world.spec["minimum_steps"])
    return {
        "steps_left": left,
        "settled": question_settled(world),
        "bar": None if left < minimum else informativeness_bar(world, left),
    }
