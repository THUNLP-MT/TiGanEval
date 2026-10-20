"""Saving the query cache onto the device and reading it back.

The background writer calls `save` while the crew works, so a slot holds
whatever the query looked like at that instant. `restore_one` is what a screen's
first load asks before it goes to the depot. `restore_all` is the rebuild the
app runs when the process starts, so a van that opens the app cold has its
screens before anything reaches the depot.
"""

from __future__ import annotations

from typing import Any

from .protocol import (
    Clock,
    DeviceStore,
    EventLog,
    PersistConfig,
    QueryCache,
    QueryState,
    apply_success,
    cache_key,
    slot_name,
    snapshot_key,
    snapshot_payload,
    snapshot_state,
)


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
        """What the device has for this query, for the load about to run."""

        saved = self.store.read(self.slot(query_key))
        if saved is None:
            return None
        return snapshot_state(saved).data

    def restore_all(self, cache: QueryCache, clock: Clock, events: EventLog) -> int:
        """Rebuild the cache from every slot on the device.

        Start-up hands this the same clock and event log every load path in the
        app is handed. This prototype uses neither.
        """

        rebuilt = 0
        for slot in self.store.slots():
            saved = self.store.read(slot)
            if saved is None:
                continue
            key = snapshot_key(saved)
            state = snapshot_state(saved)
            cache.adopt(
                key,
                apply_success(
                    cache.state(key) or QueryState(), state.data, state.data_updated_at
                ),
            )
            rebuilt += 1
        return rebuilt
