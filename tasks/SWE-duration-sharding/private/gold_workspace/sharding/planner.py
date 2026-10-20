"""The shard planner the CI runner calls on every machine of a run.

Every machine of a run computes the whole split from the same three things —
the set of files in the tree, the timings the run was started against, and the
shard count — and then returns its own slice. Nothing here looks at the order
this machine happened to walk the tree in, and nothing here reads a timing that
was published after the run began, so two machines of one run cannot disagree
and a machine restarted later cannot be handed different work.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    Checkout,
    History,
    HistoryEntry,
    RunContext,
    UNMEASURED_MS,
    atomic_write,
    discover,
    encode_history,
    hash_shard,
    read_history,
    timings_as_of,
)
from .support import history_lock


def plan_shards(
    checkout: Checkout,
    run: RunContext,
    history_path: str,
    index: int,
    count: int,
) -> Mapping[str, Any]:
    """Work out which files this machine runs, and report the plan."""

    files = discover(checkout)
    # The generation this run is pinned to. Every machine of the run is handed
    # the same one, a retried machine is handed the one its first attempt had,
    # and the plan says which it was, so the timing board and the run log
    # cannot end up describing two different histories.
    pinned_at = int(run.history_generation)
    estimates_for_run = _timings_published_by(history_path, pinned_at)
    mine = _split(files, estimates_for_run, int(count))[int(index)]
    # What the board holds the run against: the time this generation of the
    # history has for each file, whatever the split above made of it.
    estimates = {path: estimates_for_run.get(path, UNMEASURED_MS) for path in mine}
    return {
        "run_id": run.run_id,
        "attempt": int(run.attempt),
        "index": int(index),
        "shard_count": int(count),
        "history_generation": pinned_at,
        "files": list(mine),
        "estimates": estimates,
        "predicted_ms": sum(estimates.values()),
    }


def record_durations(
    history_path: str,
    run: RunContext,
    observations: Sequence[Mapping[str, Any]],
) -> None:
    """Add what this machine's files took to the history the next run reads."""

    with history_lock(history_path):
        _record_durations_unlocked(history_path, run, observations)


def _record_durations_unlocked(
    history_path: str,
    run: RunContext,
    observations: Sequence[Mapping[str, Any]],
) -> None:
    """Merge one publication while holding the history's publication lock."""

    history = read_history(history_path)
    entries = (
        {path: list(observed) for path, observed in history.entries.items()}
        if history is not None
        else {}
    )
    generation = max(
        history.generation if history is not None else 0, int(run.history_generation)
    ) + 1
    written = False
    for observation in observations:
        # A file that was skipped or died part way through spent no time that
        # says anything about the file, so it leaves the history as it was.
        if str(observation.get("status")) != "completed":
            continue
        # Added to what the file already holds: the other machines of this run
        # are writing here too, and the run that started before them still has
        # to see what it started with.
        entries.setdefault(str(observation.get("file")), []).append(
            HistoryEntry(
                duration_ms=int(observation.get("duration_ms", 0)),
                generation=generation,
                recorded_at=float(run.now),
            )
        )
        written = True
    if not written:
        return
    atomic_write(
        history_path,
        encode_history(
            History(
                generation=generation,
                entries={path: tuple(observed) for path, observed in entries.items()},
            )
        ),
    )


def _timings_published_by(history_path: str, generation: int) -> dict[str, int]:
    """What the history held at `generation`, and nothing published since."""

    return timings_as_of(read_history(history_path), generation)


def _split(
    files: Sequence[str], estimates: Mapping[str, int], count: int
) -> dict[int, list[str]]:
    """The whole run's assignment, from the file set alone."""

    suite = sorted(set(str(path) for path in files))
    timed = [path for path in suite if path in estimates]
    untimed = [path for path in suite if path not in estimates]
    shards: dict[int, list[str]] = {index: [] for index in range(1, count + 1)}
    loads: dict[int, int] = {index: 0 for index in range(1, count + 1)}
    # Nothing has ever timed these, so leaving them where the split CI has
    # always had them keeps every shard's build cache and quarantine list
    # pointing at the files it was built for.
    for index in range(1, count + 1):
        shards[index].extend(hash_shard(untimed, index, count))
    # Longest first onto the shard with the least on it; the lowest index takes
    # a tie, so the answer never depends on which machine is asking.
    for path in sorted(timed, key=lambda item: (-estimates[item], item)):
        index = min(range(1, count + 1), key=lambda item: (loads[item], item))
        shards[index].append(path)
        loads[index] += estimates[path]
    return {index: sorted(paths) for index, paths in shards.items()}
