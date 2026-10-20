"""Runtime contract for the CI shard planner.

Everything in this file is shared with the CI runner, the build-cache key and
the flaky-test quarantine list, and it ships in the runner's release rather
than ours. A run of the suite is `shard_count` machines that never talk to each
other: each one walks the working tree, works out which slice of the suite is
its own, runs it, and writes what its files took into the duration history the
next run reads. The only thing the machines of one run share is that file.

Everything here is deterministic. A run's clock reading comes from
`RunContext.now` rather than from the machine, because a replay of a run has to
reproduce that run exactly, and the split for a file comes from a digest of its
path rather than from `hash()`, which is salted per process.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence


#: Where the duration history lives, relative to the working tree root.
DEFAULT_HISTORY_PATH = "duration-history.json"

#: The price a plan puts on a file the history has no time for. It is a
#: statement about the history rather than about the planner: a file the plan's
#: own generation of the history has a time for is priced at that time, whatever
#: the planner then did with it.
UNMEASURED_MS = 0

#: What a shard reports back about one file it was handed. Only a file that ran
#: to completion has a timing that says anything about the file.
RUN_STATUSES: tuple[str, ...] = ("completed", "skipped", "crashed")

#: The fields the runner reads out of a plan before it starts a shard.
#: ``estimates`` is the plan's price for each file it assigns, and
#: ``predicted_ms`` their total; the timing board reads both back against what
#: the shard cost, so a price quotes the history the plan names rather than the
#: planner's own weighting of the file.
PLAN_FIELDS: tuple[str, ...] = (
    "run_id", "attempt", "index", "shard_count",
    "history_generation", "files", "predicted_ms", "estimates",
)


class ShardingError(RuntimeError):
    pass


class PlanError(ShardingError):
    """A plan the runner cannot read, so it will not start the shard."""


@dataclass(frozen=True, slots=True)
class Checkout:
    """One machine's view of the working tree.

    ``files`` is what this machine's walk of ``root`` returned, in the order it
    returned them.
    """

    root: str
    files: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Checkout":
        return cls(root=str(value.get("root", ".")),
                   files=tuple(str(item) for item in value.get("files", ())))

    def as_dict(self) -> dict[str, Any]:
        return {"root": self.root, "files": list(self.files)}


def discover(checkout: Checkout) -> tuple[str, ...]:
    """The spec files this machine found, in the order its walk returned them.

    The CI image and a developer laptop enumerate the same directory in
    different orders, and so do two CI images with different layer caches, so
    the machines of one run rarely see this sequence the same way. What they do
    see the same way is the set of names.
    """

    return tuple(checkout.files)


def hash_shard(files: Sequence[str], index: int, count: int) -> tuple[str, ...]:
    """The split CI has used since the suite was first sharded.

    A file belongs to ``md5(path) % count + 1``. The answer is returned in path
    order and does not depend on the order the caller found the files in, so
    every machine of a run agrees on it without talking to any other.
    """

    count = int(count)
    index = int(index)
    if count < 1:
        raise ShardingError(f"shard count must be at least 1: {count}")
    if not 1 <= index <= count:
        raise ShardingError(f"shard index {index} is outside 1..{count}")
    chosen = []
    for path in sorted({str(item) for item in files}):
        digest = hashlib.md5(path.encode("utf-8")).hexdigest()
        if int(digest, 16) % count + 1 == index:
            chosen.append(path)
    return tuple(chosen)


@dataclass(frozen=True, slots=True)
class RunContext:
    """What the runner tells every machine about the run it belongs to.

    ``history_generation`` is the generation the duration history was at when
    this run started; every machine of the run is given the same number, and a
    retried machine is given the number the first attempt was given.
    ``now`` is the run's clock reading in seconds.
    """

    run_id: str
    attempt: int
    history_generation: int
    now: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RunContext":
        return cls(run_id=str(value["run_id"]), attempt=int(value.get("attempt", 1)),
                   history_generation=int(value.get("history_generation", 0)),
                   now=float(value.get("now", 0.0)))

    def as_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "attempt": self.attempt,
                "history_generation": self.history_generation, "now": self.now}


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One observation of one file: what it took on one run.

    ``generation`` is the generation this observation was published in, and
    ``recorded_at`` is the clock reading of the run that made it. A file
    accumulates observations as runs finish; the document's own ``generation``
    is the newest of them.
    """

    duration_ms: int
    generation: int
    recorded_at: float

    def as_dict(self) -> dict[str, Any]:
        return {"duration_ms": self.duration_ms, "generation": self.generation,
                "recorded_at": self.recorded_at}


@dataclass(frozen=True, slots=True)
class History:
    """The whole duration history document.

    ``generation`` is the newest generation the document holds. ``entries``
    maps a slash-separated path relative to the working tree root to every
    observation published for that file, oldest generation first. What the
    document says a file takes is therefore a question about one generation of
    it, which :func:`timings_as_of` answers.
    """

    generation: int
    entries: Mapping[str, tuple[HistoryEntry, ...]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "entries": {
                path: [entry.as_dict() for entry in observations]
                for path, observations in sorted(self.entries.items())
            },
        }


def _whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse_history(text: str | None) -> History | None:
    """The history a document holds, or ``None`` when there is nothing usable.

    A missing file, an empty file, one a killed job left half written, and one
    whose shape the runner does not know all come back as ``None``: there is no
    partial answer to give, and a caller that gets ``None`` has no timings.
    """

    if not isinstance(text, str) or not text.strip():
        return None
    try:
        raw = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(raw, Mapping):
        return None
    generation, entries = raw.get("generation"), raw.get("entries")
    if not _whole(generation) or not isinstance(entries, Mapping):
        return None
    parsed: dict[str, tuple[HistoryEntry, ...]] = {}
    for path, value in entries.items():
        if not isinstance(path, str) or isinstance(value, (str, bytes)):
            return None
        if not isinstance(value, Sequence) or not value:
            return None
        observations: list[HistoryEntry] = []
        for item in value:
            if not isinstance(item, Mapping):
                return None
            duration, stamped = item.get("duration_ms"), item.get("generation")
            recorded_at = item.get("recorded_at")
            if not _whole(duration) or not _whole(stamped):
                return None
            if not isinstance(recorded_at, (int, float)) or isinstance(recorded_at, bool):
                return None
            observations.append(HistoryEntry(duration_ms=int(duration), generation=int(stamped),
                                             recorded_at=float(recorded_at)))
        parsed[path] = tuple(
            sorted(observations, key=lambda entry: (entry.generation, entry.recorded_at))
        )
    return History(generation=int(generation), entries=parsed)


def timings_as_of(history: History | None, generation: int) -> dict[str, int]:
    """What one generation of the history says each file takes.

    A file accumulates observations, so "what the history holds for this file"
    is only a question with an answer once a generation is named: the answer is
    the newest observation published at or before ``generation``, and the file
    is absent when every observation it has was published after it. This is how
    the timing board reads a run's numbers back — a run is planned and priced
    against the generation it started at, and what landed on top of it belongs
    to the run that published it.
    """

    if history is None:
        return {}
    held: dict[str, int] = {}
    for path, observed in history.entries.items():
        published = [entry for entry in observed if entry.generation <= int(generation)]
        if published:
            newest = max(published, key=lambda entry: (entry.generation, entry.recorded_at))
            held[str(path)] = int(newest.duration_ms)
    return held


def encode_history(history: History) -> str:
    """The document text for one history, in the runner's canonical form."""

    return json.dumps(history.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def read_history(path: str | os.PathLike[str]) -> History | None:
    """Read and parse the history file, or ``None`` when there is none to use."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return parse_history(text)


def atomic_write(path: str | os.PathLike[str], text: str) -> None:
    """Publish ``text`` at ``path`` in one step.

    A job killed part way through must leave the file it was replacing intact
    rather than half of the new one, so the text is written beside the target
    and renamed over it.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.",
                                         suffix=".part")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def require_plan(report: Any) -> dict[str, Any]:
    """Read a plan the way the runner reads it before it starts a shard.

    The runner refuses to start a machine whose plan it cannot read, because a
    machine that runs an unreadable plan is a machine nobody can account for
    afterwards. What it reads out of ``estimates`` is the plan's price for each
    file it assigns and for no others: the time ``timings_as_of`` finds for that
    file at ``history_generation``, and ``UNMEASURED_MS`` when that generation
    holds none. ``predicted_ms`` is their total. The board holds those numbers against
    what the shard cost, so they say what the history said and not what the
    planner made of it: a plan that keeps the split CI has always had still
    quotes the history for the files the history has timed. Returns the plan in
    normal form; raises :class:`PlanError` naming what is wrong.
    """

    if not isinstance(report, Mapping):
        raise PlanError(f"a plan must be a mapping, not {type(report).__name__}")
    missing = [name for name in PLAN_FIELDS if name not in report]
    if missing:
        raise PlanError("the plan does not carry " + ", ".join(missing))

    def whole(name: str, minimum: int) -> int:
        value = report[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise PlanError(f"{name} must be a whole number of at least {minimum}: {value!r}")
        return int(value)

    run_id = report["run_id"]
    if not isinstance(run_id, str) or not run_id.strip():
        raise PlanError(f"run_id must name the run: {run_id!r}")
    attempt = whole("attempt", 1)
    shard_count = whole("shard_count", 1)
    index = whole("index", 1)
    if index > shard_count:
        raise PlanError(f"shard index {index} is outside 1..{shard_count}")
    generation = whole("history_generation", 0)
    predicted = whole("predicted_ms", 0)

    raw_files = report["files"]
    if isinstance(raw_files, (str, bytes)) or not isinstance(raw_files, Sequence):
        raise PlanError(f"files must be a sequence of paths: {raw_files!r}")
    files = []
    for item in raw_files:
        if not isinstance(item, str) or not item:
            raise PlanError(f"files must hold paths: {item!r}")
        files.append(item)

    raw_estimates = report["estimates"]
    if not isinstance(raw_estimates, Mapping):
        raise PlanError(f"estimates must map a path to whole milliseconds: {raw_estimates!r}")
    estimates: dict[str, int] = {}
    for path, value in raw_estimates.items():
        if not isinstance(path, str) or not path:
            raise PlanError(f"estimates must be keyed by path: {path!r}")
        if not _whole(value):
            raise PlanError(f"the estimate for {path} must be whole milliseconds: {value!r}")
        estimates[path] = int(value)

    return {
        "run_id": run_id, "attempt": attempt, "index": index, "shard_count": shard_count,
        "history_generation": generation, "files": tuple(files), "predicted_ms": predicted,
        "estimates": estimates,
    }


__all__ = (
    "Checkout", "DEFAULT_HISTORY_PATH", "History", "HistoryEntry", "PLAN_FIELDS", "PlanError",
    "RUN_STATUSES", "RunContext", "ShardingError", "UNMEASURED_MS", "atomic_write", "discover",
    "encode_history", "hash_shard", "parse_history", "read_history", "require_plan",
    "timings_as_of",
)
