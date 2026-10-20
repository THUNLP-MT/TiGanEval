"""The shard planner the CI runner calls on every machine of a run.

Sort the files by the time they last took, longest first, and fill the shards
greedily. On a fresh tree there is nothing to sort by, so deal the files out
evenly and let the next run correct itself. At the end of the run each machine
writes what its files took into the duration history.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .protocol import Checkout, RunContext, discover, read_history


def plan_shards(
    checkout: Checkout,
    run: RunContext,
    history_path: str,
    index: int,
    count: int,
) -> Mapping[str, Any]:
    """Work out which files this machine runs."""

    files = list(discover(checkout))
    history = read_history(history_path)
    recorded = (
        {}
        if history is None
        else {path: observed[-1].duration_ms for path, observed in history.entries.items()}
    )
    if not recorded:
        mine = _even_deal(files, int(index), int(count))
    else:
        mine = _greedy(files, recorded, int(index), int(count))
    # What this machine is expected to cost: the time each of its files last
    # took, and the total of those, so the cost report has a number to hold the
    # run against.
    estimates = {path: int(recorded.get(path, 0)) for path in mine}
    return {
        "run_id": run.run_id,
        "attempt": int(run.attempt),
        "index": int(index),
        "shard_count": int(count),
        "history_generation": int(run.history_generation),
        "files": mine,
        "estimates": estimates,
        "predicted_ms": sum(estimates.values()),
    }


def record_durations(
    history_path: str,
    run: RunContext,
    observations: Sequence[Mapping[str, Any]],
) -> None:
    """Write what this machine's files took into the duration history."""

    document = {
        "generation": int(run.history_generation),
        "entries": {
            str(observation.get("file")): [
                {
                    "duration_ms": int(observation.get("duration_ms", 0)),
                    "generation": int(run.history_generation),
                    "recorded_at": float(run.now),
                }
            ]
            for observation in observations
        },
    }
    Path(history_path).write_text(
        json.dumps(document, indent=2, sort_keys=True), encoding="utf-8"
    )


def _even_deal(files: Sequence[str], index: int, count: int) -> list[str]:
    return [path for position, path in enumerate(files) if position % count == index - 1]


def _greedy(
    files: Sequence[str], recorded: Mapping[str, int], index: int, count: int
) -> list[str]:
    shards: dict[int, list[str]] = {shard: [] for shard in range(1, count + 1)}
    loads: dict[int, int] = {shard: 0 for shard in range(1, count + 1)}
    for path in sorted(files, key=lambda item: -recorded.get(item, 0)):
        shard = min(range(1, count + 1), key=lambda item: (loads[item], item))
        shards[shard].append(path)
        loads[shard] += recorded.get(path, 0)
    return shards[index]
