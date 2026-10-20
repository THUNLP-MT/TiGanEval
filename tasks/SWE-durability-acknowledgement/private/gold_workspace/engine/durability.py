"""The write path's durability tracker.

Durability is established by an fsync that covers a record's byte range, not
by applying the record, and one fsync covers whatever the pipeline had
buffered. So the tracker keeps every appended record pending, and each sync
completion releases the pending records the device has now taken.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from engine import protocol


class DurabilityTracker:
    """Tracks what the log holds and releases clients from that, only."""

    def __init__(self) -> None:
        self._listener: Callable[[Any], None] | None = None
        self._pending: list[protocol.Record] = []
        self._waiters: list[protocol.Waiter] = []
        self._watermark = 0
        self._err: str | None = None
        self._events = 0

    # -- hooks -------------------------------------------------------------

    def set_listener(self, listener: Callable[[Any], None] | None) -> None:
        self._listener = listener

    def on_append(self, record: protocol.Record) -> None:
        # Applying a record proves nothing about the device; remember where it
        # sits so a later fsync can be matched against it.
        self._pending.append(record)

    def on_sync_complete(self, synced_offset: int, err: str | None) -> None:
        if err is not None and self._err is None:
            self._err = str(err)
        if self._err is None:
            offset = int(synced_offset)
            covered = [record for record in self._pending if record.end_offset <= offset]
            self._pending = [record for record in self._pending if record.end_offset > offset]
            if covered:
                self._watermark = max(self._watermark, max(record.seq for record in covered))
            for record in covered:
                if record.requests_sync:
                    self._emit(record, None)
            self._settle()
            return
        # The log has a hole in it. Nothing after it can ever be durable, so
        # every commit still waiting on the device is finished with the error.
        stranded = [record for record in self._pending if record.requests_sync]
        self._pending = []
        for record in stranded:
            self._emit(record, self._err)
        self._fail(self._err)

    def on_close(self, err: str | None) -> None:
        self._fail(err or "the node closed")

    # -- what the ack path asks --------------------------------------------

    def wait_for_durability(self, seq: int) -> protocol.Waiter:
        waiter = protocol.Waiter(seq)
        if waiter.seq <= self._watermark:
            waiter.resolve()
        elif self._err is not None:
            waiter.resolve(self._err)
        else:
            self._waiters.append(waiter)
        return waiter

    def durable_state(self) -> protocol.DurableState:
        return protocol.DurableState(self._watermark, self._err)

    def durability_stats(self) -> Mapping[str, int]:
        return {"pending_waiters": len(self._waiters), "durability_events": self._events}

    # -- internals ---------------------------------------------------------

    def _emit(self, record: protocol.Record, err: str | None) -> None:
        event = protocol.DurabilityEvent(
            seq=record.seq,
            correlation_id=record.correlation_id,
            size=len(protocol.encode_batch(record.batch)),
            key_count=protocol.key_count(record.batch),
            err=err,
        )
        self._events += 1
        if self._listener is not None:
            self._listener(event)

    def _settle(self) -> None:
        waiting: list[protocol.Waiter] = []
        for waiter in self._waiters:
            if waiter.seq <= self._watermark:
                waiter.resolve()
            else:
                waiting.append(waiter)
        self._waiters = waiting

    def _fail(self, err: str | None) -> None:
        outstanding, self._waiters = self._waiters, []
        for waiter in outstanding:
            waiter.resolve(err)
