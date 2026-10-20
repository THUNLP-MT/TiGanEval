"""Saving the query cache onto the device and reading it back.

A restored query is the query the crew left, not a fresh load that happens to
reuse old rows. Both ways in -- the load that asks the device first and the
rebuild the app runs at start-up -- adopt the whole saved state through the same
two steps, so the same slot puts the same screen up whichever one ran; and a
rebuild over a query this process already holds keeps the newer rows and the
newer trouble rather than swapping one for the other.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .protocol import (
    IDLE,
    Clock,
    DeviceStore,
    EventLog,
    PersistConfig,
    QueryCache,
    QueryState,
    StoredCopy,
    cache_key,
    slot_name,
    snapshot_key,
    snapshot_payload,
    snapshot_state,
    status_for,
)


def settled(state: QueryState) -> QueryState:
    """A saved state as a query this process can hold.

    Whatever load the writer caught belonged to a process that is gone, so
    nothing is running and the screen must not wait on it; and the status is
    what the saved data and error mean, whatever the writer had got round to
    writing when it caught them.
    """

    return replace(
        state,
        fetch_status=IDLE,
        status=status_for(state.data, state.error),
    )


def merged(live: QueryState | None, saved: QueryState) -> QueryState:
    """One saved state over a query this process already holds.

    The two sides are read on their own stamps and nothing moves backwards:
    whichever side saw the rows last keeps the rows, their stamp and their
    count; whichever side saw the trouble last keeps the error, its reason, its
    stamp, its count and the retry counter; and the status is what the surviving
    pair means, so newer rows under an older error are still an error over rows.
    """

    if live is None:
        return settled(saved)
    rows = saved if int(saved.data_updated_at) > int(live.data_updated_at) else live
    trouble = saved if int(saved.error_updated_at) > int(live.error_updated_at) else live
    both = QueryState(
        data=rows.data,
        data_updated_at=int(rows.data_updated_at),
        data_update_count=int(rows.data_update_count),
        is_invalidated=bool(rows.is_invalidated),
        error=trouble.error,
        error_updated_at=int(trouble.error_updated_at),
        error_update_count=int(trouble.error_update_count),
        failure_count=int(trouble.failure_count),
        failure_reason=trouble.failure_reason,
    )
    return settled(both)


class Persister:
    """The query cache's side of the device store."""

    def __init__(self, store: DeviceStore, config: PersistConfig | None = None):
        self.store = store
        self.config = config or PersistConfig()

    def slot(self, query_key: Any) -> str:
        return slot_name(self.config.prefix, cache_key(query_key))

    def save(self, query_key: Any, state: QueryState) -> None:
        """Write one query onto the device."""

        self.store.write(self.slot(query_key), snapshot_payload(query_key, state))

    def restore_one(self, query_key: Any) -> Any:
        """What the device has for this query, for the load about to run.

        The whole saved state goes back, marked as having come off the device,
        so the screen is the one the crew left and nothing counts as a load that
        finished.
        """

        saved = self.store.read(self.slot(query_key))
        if saved is None:
            return None
        return StoredCopy(state=settled(snapshot_state(saved)))

    def restore_all(self, cache: QueryCache, clock: Clock, events: EventLog) -> int:
        """Rebuild the cache from every slot on the device.

        Nothing here reached the depot, so nothing is reported as a load that
        finished and nothing is stamped from the clock: each slot is adopted
        over whatever this process already holds for that query.
        """

        rebuilt = 0
        for slot in self.store.slots():
            saved = self.store.read(slot)
            if saved is None:
                continue
            key = snapshot_key(saved)
            cache.adopt(key, merged(cache.state(key), snapshot_state(saved)))
            rebuilt += 1
        return rebuilt
