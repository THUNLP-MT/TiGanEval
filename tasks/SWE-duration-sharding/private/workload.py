'Deterministic suites, duration draws, and CI run programs.'

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Mapping, Sequence


AREAS = ("billing", "checkout", "search", "accounts", "reporting", "notifications",
         "admin", "mobile")
LEAVES = ("smoke", "edge_cases", "permissions", "pagination", "totals", "refunds",
          "imports", "exports", "filters", "history", "limits", "webhooks")


SHAPE = (
    34.0, 22.0, 16.0, 12.0, 9.5, 9.5, 6.5, 6.5, 4.5, 4.5, 3.2, 3.2,
    2.4, 2.4, 1.7, 1.7, 1.3, 1.3, 0.95, 0.95, 0.7, 0.7, 0.5, 0.5,
)

NEW_SHAPE = (14.0, 11.0, 8.0, 6.0, 4.5, 3.5, 2.8, 2.2, 1.7, 1.3, 0.9, 0.5)


SECOND_SCALE = 10

SUITE_SIZE = len(SHAPE)
NEW_SIZE = len(NEW_SHAPE)

SMALL_BRANCH_SIZE = 3
SHARD_COUNT = 4
BALANCE_RATIO = 1.25


def _stream(*parts: Any) -> random.Random:
    key = "|".join(str(part) for part in parts).encode("utf-8")
    return random.Random(int(hashlib.md5(key).hexdigest(), 16))


def _catalogue(seed: int) -> list[str]:
    paths = [f"tests/{area}/{leaf}_spec.ts" for area in AREAS for leaf in LEAVES]
    _stream("catalogue", seed).shuffle(paths)
    return paths


def suite(seed: int, size: int, offset: int = 0) -> tuple[str, ...]:
    'The spec files in the working tree, as a set with no order promised.'

    return tuple(_catalogue(seed)[offset : offset + size])


def durations(seed: int, files: Sequence[str], shape: Sequence[float]) -> dict[str, int]:
    'What each file actually takes, in milliseconds.'

    positions = list(range(len(files)))
    _stream("durations", seed).shuffle(positions)
    return {
        files[position]: int(round(shape[slot] * SECOND_SCALE * 1000))
        for slot, position in enumerate(positions)
    }


def walk_order(seed: int, files: Sequence[str], label: str) -> list[str]:
    "The order one machine's walk of the tree returned the files in."

    order = list(files)
    _stream("walk", seed, label).shuffle(order)
    return order


def _document(generation: int, durations_ms: Mapping[str, int], recorded_at: float) -> dict[str, Any]:
    stamp = {"generation": int(generation), "recorded_at": float(recorded_at)}
    return {
        "generation": int(generation),
        "entries": {path: [{"duration_ms": int(value), **stamp}]
                    for path, value in sorted(durations_ms.items())},
    }


def _history(label: str, document: Any) -> dict[str, Any]:
    'What the shared history file holds when the next step starts.'

    if document is None or isinstance(document, str):
        return {"type": "history_set", "label": label, "text": document}
    return {"type": "history_set", "label": label,
            "text": json.dumps(document, indent=2, sort_keys=True)}


def _run(run_id: str, attempt: int, generation: int, now: float) -> dict[str, Any]:
    return {"run_id": run_id, "attempt": int(attempt),
            "history_generation": int(generation), "now": float(now)}


def _plans(seed: int, files: Sequence[str], group: str, run: Mapping[str, Any],
           count: int) -> list[dict[str, Any]]:
    return [
        {"type": "plan", "label": f"{group}-shard-{index}", "group": group, "index": index,
         "count": count, "run": dict(run),
         "order": walk_order(seed, files, f"{group}-{index}")}
        for index in range(1, count + 1)
    ]


def _shard_runs(group: str, count: int, run: Mapping[str, Any], *,
                indices: Sequence[int] | None = None, skipped: Sequence[str] = (),
                crashed: Sequence[str] = (), record: bool = True) -> list[dict[str, Any]]:
    shards = list(indices if indices is not None else range(1, count + 1))
    events: list[dict[str, Any]] = [
        {"type": "shard_run", "label": f"{group}-ran-{index}", "group": group, "index": index,
         "skipped_files": list(skipped), "crashed_files": list(crashed)}
        for index in shards
    ]
    if not record:
        return events
    for index in shards:
        events.append({"type": "record", "label": f"{group}-wrote-{index}", "group": group,
                       "index": index, "run": dict(run)})
        events.append({"type": "snapshot", "label": f"{group}-history-after-{index}"})
    return events


def _checkout(label: str, files: Sequence[str], true_ms: Mapping[str, int]) -> dict[str, Any]:
    return {"type": "checkout", "label": label, "files": list(files),
            "durations": {path: int(value) for path, value in true_ms.items()}}


def _baseline(seed: int) -> list[dict[str, Any]]:
    files = suite(seed, SUITE_SIZE)
    true_ms = durations(seed, files, SHAPE)
    gone = suite(seed, 6, offset=SUITE_SIZE + NEW_SIZE)
    hotfix = suite(seed, 4, offset=SUITE_SIZE + NEW_SIZE + 6)
    hotfix_ms = durations(seed + 3, hotfix, NEW_SHAPE)
    fresh = _run("ci-3180", 1, 0, 61200.0)
    killed = _run("ci-3184", 1, 0, 64800.0)
    renamed = _run("ci-3191", 1, 5, 68400.0)
    small = _run("ci-3202", 1, 0, 72000.0)
    events = [_checkout("tree-main", files, true_ms), _history("no-history-file", None)]
    events += _plans(seed, files, "fresh", fresh, SHARD_COUNT)
    events += _shard_runs("fresh", SHARD_COUNT, fresh)
    events += [_history("killed-mid-write",
                        '{\n  "generation": 1,\n  "entries": {\n    "tests/billing/tot')]
    events += _plans(seed, files, "killed", killed, SHARD_COUNT)
    events += [_history("history-after-the-rename",
                        _document(5, durations(seed + 1, gone, NEW_SHAPE), 57600.0))]
    events += _plans(seed, files, "renamed", renamed, SHARD_COUNT)
    events += [
        _checkout("tree-hotfix", hotfix, hotfix_ms),
        _history("no-history-on-the-hotfix-branch", None),
    ]
    events += _plans(seed, hotfix, "hotfix", small, 6)
    return events


def _retry(seed: int) -> list[dict[str, Any]]:
    files = suite(seed, SUITE_SIZE)
    true_ms = durations(seed, files, SHAPE)
    run = _run("ci-4471", 1, 11, 75600.0)
    again = _run("ci-4471", 2, 11, 77400.0)
    events = [_checkout("tree-main", files, true_ms),
              _history("history-at-the-start-of-the-run", _document(11, true_ms, 72000.0))]
    events += _plans(seed, files, "first-pass", run, SHARD_COUNT)
    events += _shard_runs("first-pass", SHARD_COUNT, run, indices=(1, 2, 4))
    events += [{"type": "history_publish", "generation": 12, "recorded_at": 76200.0,
                "label": "the-nightly-run-published-while-shard-3-was-down",
                "durations": {path: int(true_ms[path] * 2) for path in sorted(files)[:5]}}]
    events += _plans(seed, files, "re-planned", run, SHARD_COUNT)[:1]
    events += [
        {"type": "plan", "label": "retried-shard-3", "group": "retry", "index": 3,
         "count": SHARD_COUNT, "run": dict(again), "order": walk_order(seed, files, "retry-3")},
        {"type": "snapshot", "label": "history-at-the-end"},
    ]
    return events


def _concurrent(seed: int) -> list[dict[str, Any]]:
    files = suite(seed, SUITE_SIZE)
    true_ms = durations(seed, files, SHAPE)
    run = _run("ci-5120", 1, 20, 82800.0)
    ordered = sorted(files)
    skipped = [ordered[0]]
    crashed = [ordered[1]]
    events = [_checkout("tree-main", files, true_ms),
              _history("history-at-the-start-of-the-run", _document(20, true_ms, 79200.0))]
    events += _plans(seed, files, "all-four", run, SHARD_COUNT)
    events += _shard_runs("all-four", SHARD_COUNT, run, skipped=skipped,
                          crashed=crashed, record=False)
    events += [{"type": "record_group", "label": "all-four-finished-together",
                "group": "all-four", "indices": list(range(1, SHARD_COUNT + 1)),
                "run": dict(run)},
               {"type": "snapshot", "label": "history-after-all-four-finished"}]
    return events


def _newfiles(seed: int) -> list[dict[str, Any]]:
    files = suite(seed, SUITE_SIZE)
    true_ms = durations(seed, files, SHAPE)
    added = suite(seed, NEW_SIZE, offset=SUITE_SIZE)
    added_ms = durations(seed + 1, added, NEW_SHAPE)
    whole = tuple(files) + tuple(added)
    everything = {**true_ms, **added_ms}
    run = _run("ci-6300", 1, 30, 86400.0)
    events = [_checkout("tree-with-the-branch", whole, everything),
              _history("history-covers-only-what-was-there-before",
                       _document(30, true_ms, 84600.0))]
    events += _plans(seed, whole, "branch", run, SHARD_COUNT)
    events += _shard_runs("branch", SHARD_COUNT, run, record=False)
    events += [{"type": "snapshot", "label": "history-at-the-end"}]
    return events


def _smallpr(seed: int) -> list[dict[str, Any]]:
    'A three-file pull request, with the nightly landing while it runs.'

    files = suite(seed, SUITE_SIZE)
    true_ms = durations(seed, files, SHAPE)
    added = suite(seed, SMALL_BRANCH_SIZE, offset=SUITE_SIZE + NEW_SIZE + 10)
    added_ms = durations(seed + 2, added, NEW_SHAPE)
    whole = tuple(files) + tuple(added)
    everything = {**true_ms, **added_ms}
    run = _run("ci-7410", 1, 40, 90000.0)
    events = [_checkout("tree-with-the-pull-request", whole, everything),
              _history("history-covers-what-was-there-before-the-pull-request",
                       _document(40, true_ms, 88200.0))]
    events += _plans(seed, whole, "small-branch", run, SHARD_COUNT)
    events += [{"type": "history_publish", "generation": 41, "recorded_at": 90600.0,
                "label": "the-nightly-run-published-while-this-one-was-still-planning",
                "durations": {path: int(true_ms[path] * 3) for path in sorted(files)[:7]}},
               {"type": "plan", "label": "the-machine-that-came-up-late", "group": "small-branch-late",
                "index": 2, "count": SHARD_COUNT, "run": dict(run),
                "order": walk_order(seed, whole, "small-branch-late-2")},
               {"type": "snapshot", "label": "history-at-the-end"}]
    return events


PHASE_BUILDERS = {
    "baseline": _baseline,
    "retry": _retry,
    "concurrent": _concurrent,
    "newfiles": _newfiles,
    "smallpr": _smallpr,
}


def build_program(profile: str, seed: int) -> list[dict[str, Any]]:
    if profile == "release":
        program: list[dict[str, Any]] = []
        for phase in ("baseline", "retry", "concurrent", "newfiles", "smallpr"):
            for event in PHASE_BUILDERS[phase](seed):
                program.append({**event, "phase": phase})
        return program
    builder = PHASE_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown CI program profile: {profile}")
    return [{**event, "phase": profile} for event in builder(seed)]
