"""Runtime contract for the Kerbside handset's query cache.

Every build of the field app ships this file -- the handset, the crew tablet and
the depot's web console -- so the value types, the screen the crew reads, the
device store and the load driver below are identical in all three. Time moves
only when the console moves it, what the depot answers comes from the console's
script, and nothing reaches the depot except through :func:`run_query`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence


#: What a query's ``status`` says about the (data, error) pair it holds.
PENDING, SUCCESS, ERROR = "pending", "success", "error"

#: What a query's ``fetch_status`` says about a load running right now. The
#: screen shows a spinner while this is anything but ``idle``; ``paused`` is
#: what the app writes when a load is waiting for the van to find signal.
IDLE, FETCHING, PAUSED = "idle", "fetching", "paused"


class DepotUnreachable(RuntimeError):
    """A load could not reach the depot at all."""


@dataclass(frozen=True, slots=True)
class QueryState:
    """Everything the app holds about one query.

    This is the value the background writer saves into a device slot, and the
    value a restore has to put back. ``data`` is whatever the screen renders;
    ``error`` is the last thing that went wrong with it; ``status`` is what the
    pair means; ``fetch_status`` describes a load that is running right now. The
    counters and stamps are what the "last updated" line and the retry banner
    are built from."""
    data: Any = None
    error: str | None = None
    status: str = PENDING
    fetch_status: str = IDLE
    failure_count: int = 0
    failure_reason: str | None = None
    data_updated_at: int = 0
    error_updated_at: int = 0
    data_update_count: int = 0
    error_update_count: int = 0
    is_invalidated: bool = False


#: The fields of :class:`QueryState`, in the order the writer stores them.
STATE_FIELDS: tuple[str, ...] = (
    "data", "error", "status", "fetch_status", "failure_count", "failure_reason",
    "data_updated_at", "error_updated_at", "data_update_count", "error_update_count",
    "is_invalidated",
)


def status_for(data: Any, error: str | None) -> str:
    """What a (data, error) pair means.

    Every state the app writes takes its ``status`` from here, so a query whose
    status is not this of its own data and error is showing the crew something
    the query does not hold."""
    if error is not None:
        return ERROR
    return SUCCESS if data is not None else PENDING


def page_cursors(data: Any) -> list[str]:
    """The cursors a paginated screen's "Load more" button reads.

    A paginated query holds ``{"pages": [...], "cursors": [...]}`` and asks for
    the next page with the last cursor. Anything else has no cursors, and a
    screen with none starts its list again from the top."""
    if isinstance(data, Mapping):
        cursors = data.get("cursors")
        if isinstance(cursors, Sequence) and not isinstance(cursors, (str, bytes)):
            return [str(item) for item in cursors]
    return []


def derive_result(state: QueryState) -> dict[str, Any]:
    """The screen the crew reads, built from one query's state.

    Every list, banner, spinner and "last updated" line on a Kerbside screen is
    a field of this mapping, so two states put the same screen in front of the
    crew exactly when this mapping is equal for both."""
    has_data = state.data is not None
    is_error = str(state.status) == ERROR
    return {
        "status": str(state.status),
        "fetch_status": str(state.fetch_status),
        "data": state.data,
        "error": state.error,
        "is_error": is_error,
        "is_load_error": is_error and not has_data,
        "is_refetch_error": is_error and has_data,
        "is_pending": str(state.status) == PENDING,
        "is_fetched": int(state.data_update_count) > 0 or int(state.error_update_count) > 0,
        "spinner": str(state.fetch_status) != IDLE,
        "failure_count": int(state.failure_count),
        "failure_reason": state.failure_reason,
        "data_updated_at": int(state.data_updated_at),
        "error_updated_at": int(state.error_updated_at),
        "data_update_count": int(state.data_update_count),
        "error_update_count": int(state.error_update_count),
        "is_invalidated": bool(state.is_invalidated),
        "page_cursors": page_cursors(state.data),
    }


def apply_success(state: QueryState, data: Any, at_ms: int) -> QueryState:
    """The state a load that answered leaves behind.

    This is the ordinary fresh-success write: the rows are new, so the error and
    the retry counters that belonged to the old rows go, and the "last updated"
    stamp becomes the clock reading the answer arrived at."""
    return replace(
        state, data=data, error=None, status=status_for(data, None), fetch_status=IDLE,
        failure_count=0, failure_reason=None, data_updated_at=int(at_ms),
        data_update_count=int(state.data_update_count) + 1, is_invalidated=False)


def apply_failure(state: QueryState, message: str, at_ms: int) -> QueryState:
    """The state a load that did not answer leaves behind."""
    return replace(
        state, error=str(message), status=ERROR, fetch_status=IDLE,
        failure_count=int(state.failure_count) + 1, failure_reason=str(message),
        error_updated_at=int(at_ms), error_update_count=int(state.error_update_count) + 1)


def cache_key(query_key: Sequence[Any]) -> str:
    """The app's one name for a query, whatever screen asked for it."""
    return "|".join(str(part) for part in query_key)


def slot_name(prefix: str, key: str) -> str:
    """The device slot a query's snapshot is written to."""
    return f"{prefix}:{key}"


def snapshot_payload(query_key: Sequence[Any], state: QueryState) -> dict[str, Any]:
    """What the background writer puts in one device slot."""
    return {"key": [str(part) for part in query_key],
            "state": {name: getattr(state, name) for name in STATE_FIELDS}}


def snapshot_key(payload: Mapping[str, Any]) -> list[str]:
    """The query a stored snapshot belongs to."""
    return [str(part) for part in payload.get("key", ())]


def snapshot_state(payload: Mapping[str, Any]) -> QueryState:
    """The state the writer saved, as a value again.

    The writer runs on a timer while the crew works, so it saves whatever the
    query held at that instant and nothing tidies it afterwards."""
    saved = dict(payload.get("state") or {})
    return QueryState(**{name: saved[name] for name in STATE_FIELDS if name in saved})


@dataclass(frozen=True, slots=True)
class PersistConfig:
    """How the app names its device slots."""
    prefix: str = "kerbside"


@dataclass(frozen=True, slots=True)
class StoredCopy:
    """A persister's answer meaning: this came off the device, nothing loaded.

    :func:`run_query` adopts ``state`` as the query's state exactly as it is
    given and returns; it does not run the completion path, because no load
    finished. A persister that hands back a plain value instead is handing back
    this load's answer, and the answer goes through the completion path like any
    other."""
    state: QueryState


class DeviceStore:
    """The handset's own storage, as the app reaches it."""

    def __init__(self, initial: Mapping[str, Any] | None = None):
        self._slots = {str(k): v for k, v in dict(initial or {}).items()}
        self.reads: list[str] = []
        self.writes: list[str] = []

    def slots(self) -> list[str]:
        """Every slot on the device, in the order they were written."""
        return list(self._slots)

    def read(self, slot: str) -> dict[str, Any] | None:
        self.reads.append(str(slot))
        found = self._slots.get(str(slot))
        return None if found is None else dict(found)

    def write(self, slot: str, payload: Mapping[str, Any]) -> None:
        self.writes.append(str(slot))
        self._slots[str(slot)] = dict(payload)

    def drop(self, slot: str) -> None:
        self._slots.pop(str(slot), None)


class EventLog:
    """What the app reports about itself.

    ``load_completed`` is the counter the team watches to see how often a van
    actually reaches the depot, and the screens' own success hooks hang off the
    same completion path. ``restored`` records a screen the device answered."""

    def __init__(self) -> None:
        self.load_completed: list[dict[str, Any]] = []
        self.settled: list[dict[str, Any]] = []
        self.restored: list[dict[str, Any]] = []


class QueryCache:
    """The queries this process holds right now."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[list[str], QueryState]] = {}
        self.on_settled: list[Callable[[list[str], QueryState], None]] = []

    def keys(self) -> list[list[str]]:
        return [key for key, _ in self._entries.values()]

    def has(self, query_key: Sequence[Any]) -> bool:
        return cache_key(query_key) in self._entries

    def state(self, query_key: Sequence[Any]) -> QueryState | None:
        found = self._entries.get(cache_key(query_key))
        return None if found is None else found[1]

    def adopt(self, query_key: Sequence[Any], state: QueryState) -> None:
        """Make ``state`` this query's state, exactly as given."""
        self._entries[cache_key(query_key)] = ([str(p) for p in query_key], state)


class Clock:
    """The console's clock, in milliseconds."""

    def __init__(self, start_ms: int = 0):
        self._now = int(start_ms)

    def now_ms(self) -> int:
        return self._now

    def set(self, value: int) -> None:
        self._now = int(value)

    def advance(self, ms: int) -> None:
        self._now += int(ms)


class Depot:
    """The depot's API as this handset reaches it.

    Every call is written to :attr:`log`. What each query answers comes from the
    console's script and the last scripted answer repeats."""

    def __init__(self, script: Mapping[str, Sequence[Mapping[str, Any]]], clock: Clock):
        self.script = {str(k): [dict(s) for s in v] for k, v in dict(script).items()}
        self.clock = clock
        self.position: dict[str, int] = {}
        self.log: list[dict[str, Any]] = []

    def fetch(self, query_key: Sequence[Any]) -> Any:
        key = cache_key(query_key)
        steps = self.script.get(key) or [{"error": "no signal at this address"}]
        seen = self.position.get(key, 0)
        self.position[key] = seen + 1
        step = steps[min(seen, len(steps) - 1)]
        self.clock.advance(int(step.get("cost_ms", 10)))
        failed = "error" in step
        self.log.append({"key": key, "at_ms": self.clock.now_ms(), "answered": not failed})
        if failed:
            raise DepotUnreachable(str(step["error"]))
        return step.get("data")


def settle_fetch(
    cache: QueryCache, query_key: Sequence[Any], *, data: Any = None,
    error: str | None = None, clock: Clock, events: EventLog,
) -> QueryState:
    """Write the answer of one finished load and run the completion path.

    This is what a load that reached the depot ends in: the new state is
    written, the load-completed counter moves, and every hook the screens
    registered on the cache runs."""
    before = cache.state(query_key) or QueryState()
    after = (apply_failure(before, error, clock.now_ms()) if error is not None
             else apply_success(before, data, clock.now_ms()))
    cache.adopt(query_key, after)
    key = [str(part) for part in query_key]
    events.load_completed.append({"key": cache_key(key), "at_ms": clock.now_ms()})
    for hook in list(cache.on_settled):
        hook(key, after)
    return after


def run_query(
    cache: QueryCache, query_key: Sequence[Any], *, depot: Depot, clock: Clock,
    events: EventLog, persister: Any = None,
) -> dict[str, Any]:
    """One screen asking for its query, and the screen the crew then sees.

    The query is marked as loading, the device is asked first when the app was
    built with a persister, and the answer is either adopted as the query's
    state or settled through the completion path as a load that reached the
    depot. A pull-to-refresh runs this with no persister, because the crew asked
    for the depot and not for the device."""
    before = cache.state(query_key) or QueryState()
    cache.adopt(query_key, replace(before, fetch_status=FETCHING))
    answer = persister.restore_one(query_key) if persister is not None else None
    if isinstance(answer, StoredCopy):
        cache.adopt(query_key, answer.state)
        events.restored.append({"key": cache_key(query_key), "at_ms": clock.now_ms()})
        return derive_result(cache.state(query_key))
    if answer is not None:
        settle_fetch(cache, query_key, data=answer, clock=clock, events=events)
        return derive_result(cache.state(query_key))
    try:
        data = depot.fetch(query_key)
    except DepotUnreachable as exc:
        settle_fetch(cache, query_key, error=str(exc), clock=clock, events=events)
        return derive_result(cache.state(query_key))
    settle_fetch(cache, query_key, data=data, clock=clock, events=events)
    return derive_result(cache.state(query_key))
