"""The write path's durability tracker.

The ack path used to sleep 200ms after a commit and hope the log had caught
up. This is the prototype that replaces the sleep: it calls the listener at
the end of apply, remembers the sequence number it just applied, and lets
`wait_for_durability` return once that number has got there.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from engine import protocol


class DurabilityTracker:
    """Tracks how far the write path has got and releases clients."""

    def __init__(self) -> None:
        self._listener: Callable[[Any], None] | None = None
        self._latest = 0
        self._waiters: list[protocol.Waiter] = []
        self._events = 0

    def set_listener(self, listener: Callable[[Any], None] | None) -> None:
        self._listener = listener

    def on_append(self, record: protocol.Record) -> None:
        if self._listener is not None:
            self._listener(
                protocol.DurabilityEvent(
                    seq=record.seq,
                    correlation_id=record.correlation_id,
                    size=len(protocol.encode_batch(record.batch)),
                    key_count=protocol.key_count(record.batch),
                    err=None,
                )
            )
            self._events += 1
            self._latest = record.seq
            waiting = []
            for waiter in self._waiters:
                if waiter.seq <= self._latest:
                    waiter.resolve()
                else:
                    waiting.append(waiter)
            self._waiters = waiting

    def on_sync_complete(self, synced_offset: int, err: str | None) -> None:
        return None

    def on_close(self, err: str | None) -> None:
        return None

    def wait_for_durability(self, seq: int) -> protocol.Waiter:
        waiter = protocol.Waiter(seq)
        if int(seq) <= self._latest:
            waiter.resolve()
        else:
            self._waiters.append(waiter)
        return waiter

    def durable_state(self) -> protocol.DurableState:
        return protocol.DurableState(self._latest, None)

    def durability_stats(self) -> Mapping[str, int]:
        return {"pending_waiters": len(self._waiters), "durability_events": self._events}
