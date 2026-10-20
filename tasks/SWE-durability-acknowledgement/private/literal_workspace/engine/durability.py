"""The write path's durability tracker.

The plan the write path was given: call the listener at the end of apply,
remember that sequence number, and let `wait_for_durability(seq)` return once
the number has got there. The 200ms sleep the ack path used to do is already
gone, so this number is what answers a client instead.

`protocol.py` says `durability_events` is what this tracker produced whether
or not a listener is attached, so the count is kept outside that branch.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from engine import protocol


class DurabilityTracker:
    """Remembers the highest sequence number the write path has applied."""

    def __init__(self) -> None:
        self._listener: Callable[[Any], None] | None = None
        self._latest = 0
        self._waiters: list[protocol.Waiter] = []
        self._events = 0

    def set_listener(self, listener: Callable[[Any], None] | None) -> None:
        self._listener = listener

    def on_append(self, record: protocol.Record) -> None:
        self._latest = max(self._latest, int(record.seq))
        event = protocol.DurabilityEvent(
            seq=record.seq,
            correlation_id=record.correlation_id,
            size=len(protocol.encode_batch(record.batch)),
            key_count=protocol.key_count(record.batch),
            err=None,
        )
        self._events += 1
        if self._listener is not None:
            self._listener(event)
        self._settle()

    def on_sync_complete(self, synced_offset: int, err: str | None) -> None:
        return None

    def on_close(self, err: str | None) -> None:
        return None

    def wait_for_durability(self, seq: int) -> protocol.Waiter:
        waiter = protocol.Waiter(seq)
        if waiter.seq <= self._latest:
            waiter.resolve()
        else:
            self._waiters.append(waiter)
        return waiter

    def durable_state(self) -> protocol.DurableState:
        return protocol.DurableState(self._latest, None)

    def durability_stats(self) -> Mapping[str, int]:
        return {"pending_waiters": len(self._waiters), "durability_events": self._events}

    def _settle(self) -> None:
        waiting: list[protocol.Waiter] = []
        for waiter in self._waiters:
            if waiter.seq <= self._latest:
                waiter.resolve()
            else:
                waiting.append(waiter)
        self._waiters = waiting
