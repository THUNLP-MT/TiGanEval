"""The shard planner the CI runner calls on every machine of a run.

This is where the working prototype got to. It reads the duration history if
there is one, puts the slowest files first, and deals the list out around the
shards. Nothing writes the history back yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .protocol import Checkout, RunContext, discover


def plan_shards(
    checkout: Checkout,
    run: RunContext,
    history_path: str,
    index: int,
    count: int,
) -> Mapping[str, Any]:
    """Work out which files this machine runs, and report the plan."""

    recorded = _recorded_durations(history_path)
    files = list(discover(checkout))
    files.sort(key=lambda path: -recorded.get(path, 0))
    mine = [path for position, path in enumerate(files) if position % count == index - 1]
    return {
        "run_id": run.run_id,
        "attempt": run.attempt,
        "index": index,
        "shard_count": count,
        "history_generation": run.history_generation,
        "files": mine,
    }


def record_durations(
    history_path: str,
    run: RunContext,
    observations: Sequence[Mapping[str, Any]],
) -> None:
    """Write what this machine's files took into the duration history."""

    return None


def _recorded_durations(history_path: str) -> dict[str, int]:
    """The duration the history holds for each file."""

    try:
        raw = json.loads(Path(history_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    entries = raw.get("entries", {}) if isinstance(raw, dict) else {}
    durations: dict[str, int] = {}
    for path, value in entries.items():
        if isinstance(value, dict):
            durations[str(path)] = int(value.get("duration_ms", 0))
    return durations
