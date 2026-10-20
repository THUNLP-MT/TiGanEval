"""The storage engine's own contract: the log, the commit pipeline, the hooks.

This module ships with the storage release and is shared with the replication
feed, the recovery tool and the node console. The engine owns the write-ahead
log; a durability tracker never gets a handle to it. It learns that a record
exists when the engine calls ``on_append``, and what the device has taken when
the engine calls ``on_sync_complete``. The interface the pipeline drives::

    set_listener(listener)                  # optional; listener(event) -> None
    on_append(record)                       # one Record, already framed
    on_sync_complete(synced_offset, err)    # one fsync finished
    on_close(err)                           # the last call; nothing follows it
    wait_for_durability(seq) -> Waiter
    durable_state() -> DurableState
    durability_stats() -> Mapping[str, int]

``durability_stats()`` reports ``pending_waiters``, the waiters this tracker
has not settled yet, and ``durability_events``, how many durability events it
has produced, whether or not a listener is attached to receive them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


#: The reason the pipeline gives a tracker when the node stops.
CLOSE_REASON = "the node is closing"


@dataclass(frozen=True, slots=True)
class Record:
    """One commit, framed into the log at ``[start_offset, end_offset)``."""
    seq: int
    correlation_id: str
    batch: tuple[tuple[str, str], ...]
    start_offset: int
    end_offset: int
    requests_sync: bool


@dataclass(frozen=True, slots=True)
class SyncResult:
    """What one fsync reported: how far the device took, and any error."""
    synced_offset: int
    err: str | None


@dataclass(frozen=True, slots=True)
class DurableState:
    """The highest durable sequence number, and the first error seen."""
    watermark: int
    err: str | None


@dataclass(frozen=True, slots=True)
class DurabilityEvent:
    """A completed fsync's result for one commit that requested it."""
    seq: int
    correlation_id: str
    size: int
    key_count: int
    err: str | None


def encode_batch(batch: Sequence[Sequence[str]]) -> bytes:
    """The bytes one batch occupies in the log."""
    return ("|".join(f"{key}={value}" for key, value in batch) + "\n").encode("utf-8")


def key_count(batch: Sequence[Sequence[str]]) -> int:
    """How many distinct keys one batch writes."""
    return len({str(key) for key, _ in batch})


class Waiter:
    """A client parked on a sequence number. Whoever settles it calls
    :meth:`resolve` with an error or with nothing; every resolution is kept, so
    a handle that was settled twice still says so."""

    __slots__ = ("seq", "resolutions")

    def __init__(self, seq: int):
        self.seq = int(seq)
        self.resolutions: list[str | None] = []

    @property
    def resolved(self) -> bool:
        return bool(self.resolutions)

    @property
    def err(self) -> str | None:
        return self.resolutions[0] if self.resolutions else None

    def resolve(self, err: str | None = None) -> None:
        self.resolutions.append(None if err is None else str(err))


class WriteAheadLog:
    """Framed records plus the offset the device has acknowledged.

    ``fault_offset`` is where the first failed fsync left a hole: the device
    usually comes back and later fsyncs succeed and report a larger
    ``synced_offset``, but nothing at or after the hole is recoverable, so
    ``durable_offset`` never passes it."""

    def __init__(self) -> None:
        self.records: list[Record] = []
        self.written_offset = 0
        self.synced_offset = 0
        self.fault_offset: int | None = None
        self.fsync_log: list[SyncResult] = []
        self.armed_fault: str | None = None

    def append(self, seq: int, correlation_id: str,
               batch: Sequence[Sequence[str]], requests_sync: bool) -> Record:
        frozen = tuple((str(key), str(value)) for key, value in batch)
        start = self.written_offset
        record = Record(
            seq=int(seq),
            correlation_id=str(correlation_id),
            batch=frozen,
            start_offset=start,
            end_offset=start + len(encode_batch(frozen)),
            requests_sync=bool(requests_sync),
        )
        self.records.append(record)
        self.written_offset = record.end_offset
        return record

    def arm_fault(self, message: str) -> None:
        """Make the next fsync fail, the way a full or failing device does."""
        self.armed_fault = str(message)

    def sync(self, limit: int | None = None) -> SyncResult:
        """fsync up to ``limit`` bytes, or everything written."""
        target = self.written_offset if limit is None else min(int(limit), self.written_offset)
        if self.armed_fault is not None:
            message, self.armed_fault = self.armed_fault, None
            if self.fault_offset is None:
                self.fault_offset = self.synced_offset
            result = SyncResult(self.synced_offset, message)
        else:
            self.synced_offset = max(self.synced_offset, target)
            result = SyncResult(self.synced_offset, None)
        self.fsync_log.append(result)
        return result

    @property
    def durable_offset(self) -> int:
        if self.fault_offset is None:
            return self.synced_offset
        return min(self.synced_offset, self.fault_offset)


def recover(log: WriteAheadLog) -> tuple[Record, ...]:
    """The records a restarted node finds: those wholly below the hole."""
    limit = log.durable_offset
    return tuple(record for record in log.records if record.end_offset <= limit)


def durable_watermark(log: WriteAheadLog) -> int:
    """The highest sequence number the log holds, 0 when it holds none."""
    return max((record.seq for record in recover(log)), default=0)


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _event_row(event: Any) -> dict[str, Any]:
    read = event.get if isinstance(event, Mapping) else (lambda name: getattr(event, name, None))
    row = {name: read(name) for name in ("seq", "correlation_id", "size", "key_count", "err")}
    try:
        row["seq"] = int(row["seq"])
    except (TypeError, ValueError):
        pass
    return row


class Engine:
    """Runs one scripted session against a durability tracker.

    A session is a list of steps::

        {"op": "commit", "label": ..., "correlation_id": ..., "keys": [[k, v], ...], "sync": true}
        {"op": "flush",  "label": ..., "upto_seq": 6}      # upto_seq optional
        {"op": "fault",  "label": ..., "message": ...}     # the next fsync fails
        {"op": "wait",   "label": ..., "seq": 7}
        {"op": "regroup", "label": ..., "sync_grouping": 4}
        {"op": "probe",  "label": ...}

    A commit that asks for a sync joins the current group. When the group holds
    ``sync_grouping`` such commits the pipeline performs one fsync and reports
    it once, so one fsync covers many records and a commit that asked for
    nothing rides along inside another commit's. The group size comes from the
    pipeline's depth, not from the write path.

    ``run`` returns one telemetry row per step: the log, what recovery would
    return, what the tracker reports next to the same number computed from the
    log, the events delivered, every waiter and its resolutions, and the
    sequence numbers released so far.
    """

    def __init__(self, tracker: Any, *, listener: bool = True, sync_grouping: int = 1):
        self.tracker = tracker
        self.log = WriteAheadLog()
        self.sync_grouping = max(1, int(sync_grouping))
        self.listener_attached = bool(listener)
        self.waiters: dict[str, Any] = {}
        self.delivered: list[Any] = []
        self.steps: list[dict[str, Any]] = []
        self.released: dict[int, str] = {}
        self._step_events: list[Any] = []
        self._next_seq, self._group = 1, 0

    def _receive(self, event: Any) -> None:
        self._step_events.append(event)
        self.delivered.append(event)

    def run(self, timeline: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        start, close = {"op": "start", "label": "start"}, {"op": "close", "label": "close"}
        program = [start, *[dict(step) for step in timeline], close]
        for index, step in enumerate(program):
            op = str(step.get("op", "probe"))
            label = str(step.get("label", f"{op}-{index}"))
            row: dict[str, Any] = {"index": index, "label": label, "op": op,
                                   "ok": True, "error": None}
            self._step_events = []
            try:
                self._dispatch(op, step, row)
            except BaseException as exc:
                row["ok"], row["error"] = False, _describe(exc)
            self._observe(row)
            self.steps.append(row)
        return self.steps

    def _dispatch(self, op: str, step: Mapping[str, Any], row: dict[str, Any]) -> None:
        if op == "start":
            if self.listener_attached:
                self.tracker.set_listener(self._receive)
        elif op == "commit":
            seq = self._next_seq
            self._next_seq += 1
            record = self.log.append(
                seq,
                step.get("correlation_id", f"c-{seq:04d}"),
                [tuple(pair) for pair in step.get("keys", ())],
                bool(step.get("sync", False)),
            )
            row["commit"] = {
                "seq": record.seq,
                "correlation_id": record.correlation_id,
                "requests_sync": record.requests_sync,
                "size": record.end_offset - record.start_offset,
                "key_count": key_count(record.batch),
                "start_offset": record.start_offset,
                "end_offset": record.end_offset,
            }
            self.tracker.on_append(record)
            if record.requests_sync:
                self._group += 1
                if self._group >= self.sync_grouping:
                    self._sync(row, None)
        elif op == "flush":
            upto = step.get("upto_seq")
            limit = None
            if upto is not None:
                limit = next(
                    (r.end_offset for r in self.log.records if r.seq == int(upto)), None
                )
            self._sync(row, limit)
        elif op == "fault":
            self.log.arm_fault(str(step.get("message", "the device refused the write")))
        elif op == "wait":
            waiter = self.tracker.wait_for_durability(int(step["seq"]))
            if not hasattr(waiter, "resolutions") or not hasattr(waiter, "seq"):
                raise TypeError("wait_for_durability must return a protocol.Waiter")
            self.waiters[row["label"]] = waiter
        elif op == "regroup":
            self.sync_grouping = max(1, int(step["sync_grouping"]))
        elif op == "close":
            self.tracker.on_close(CLOSE_REASON)
        elif op != "probe":
            raise ValueError(f"unknown timeline step: {op}")

    def _sync(self, row: dict[str, Any], limit: int | None) -> None:
        target = self.log.written_offset if limit is None else int(limit)
        if target <= self.log.synced_offset and self.log.armed_fault is None:
            row["sync_skipped"] = "the device already has these bytes"
            return
        result = self.log.sync(limit)
        self._group = 0
        row["sync"] = {"synced_offset": result.synced_offset, "err": result.err}
        self.tracker.on_sync_complete(result.synced_offset, result.err)

    def _observe(self, row: dict[str, Any]) -> None:
        """What the node console records once a step is done."""
        row["log"] = {name: getattr(self.log, name) for name in
                      ("written_offset", "synced_offset", "durable_offset")}
        row["reference_watermark"] = durable_watermark(self.log)
        row["recoverable_seqs"] = [record.seq for record in recover(self.log)]
        row["reported"] = self._ask(row, self._read_state)
        row["stats"] = self._ask(
            row, lambda: {str(k): v for k, v in dict(self.tracker.durability_stats()).items()}
        )
        row["events"] = [_event_row(event) for event in self._step_events]
        row["waiters"] = [
            {"label": label, "seq": int(waiter.seq), "resolutions": list(waiter.resolutions)}
            for label, waiter in self.waiters.items()
        ]
        row["released_here"] = self._collect_released()
        row["released_so_far"] = sorted(self.released)

    def _ask(self, row: dict[str, Any], read: Any) -> dict[str, Any] | None:
        try:
            return read()
        except BaseException as exc:
            row["ok"] = False
            row["error"] = row.get("error") or _describe(exc)
            return None

    def _read_state(self) -> dict[str, Any]:
        state = self.tracker.durable_state()
        if isinstance(state, Mapping):
            return {"watermark": int(state["watermark"]), "err": state.get("err")}
        return {"watermark": int(state.watermark), "err": state.err}

    def _collect_released(self) -> list[dict[str, Any]]:
        """Sequence numbers this write path has just told somebody are safe."""
        fresh: list[dict[str, Any]] = []
        for event in self.delivered:
            item = _event_row(event)
            seq = item["seq"]
            if item["err"] is None and isinstance(seq, int) and seq not in self.released:
                self.released[seq] = "event"
                fresh.append({"seq": seq, "by": "event"})
        for label, waiter in self.waiters.items():
            resolutions = list(getattr(waiter, "resolutions", ()))
            seq = int(getattr(waiter, "seq", 0))
            if resolutions and resolutions[0] is None and seq not in self.released:
                self.released[seq] = "waiter"
                fresh.append({"seq": seq, "by": "waiter", "waiter": label})
        return fresh
