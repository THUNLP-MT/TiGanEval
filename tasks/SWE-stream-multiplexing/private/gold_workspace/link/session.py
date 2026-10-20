"""The station's end of the telemetry uplink.

One radio link carries several streams at once. Each stream owes the radio
whatever a caller handed it and may only have as much payload standing at the
depot unit as that unit has room for, so a stream whose consumer has stopped
taking bytes runs out of room and waits while the others keep going. Each round
the link is given a slot; the most urgent stream that has payload and room goes
first, streams of the same class take turns, and the frames that open and close
streams and hand room back go out ahead of payload.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from .protocol import (
    DATA, GRANT, HEADER_BYTES, OPEN, PRIORITY_NORMAL, SHUT, STATION,
    ClosedLink, LinkCounters, LinkError, SessionConfig, Write, decode_frames,
    encode_frame, grant_amount, grant_payload,
)
from .streams import Stream


class Session:
    """One radio link, carrying several streams at once."""

    def __init__(self, transport: Any, config: SessionConfig | None = None):
        self.transport = transport
        self.config = config or SessionConfig()
        self.counters = LinkCounters()
        self.streams: dict[int, Stream] = {}
        self.closed = False
        self.control: deque[bytes] = deque()
        self.order: deque[int] = deque()
        self.arrivals: deque[Stream] = deque()
        self._next_id = 1 if self.config.side == STATION else 2
        self._inbound = b""

    # -- opening and accepting streams ---------------------------------------

    def open_stream(self, priority: int = PRIORITY_NORMAL) -> Stream:
        if self.closed:
            raise ClosedLink("the link is closed")
        stream_id = self._next_id
        self._next_id += 2
        stream = self._register(stream_id, priority)
        self.control.append(encode_frame(OPEN, stream_id))
        return stream

    def accept_stream(self) -> Stream | None:
        return self.arrivals.popleft() if self.arrivals else None

    def _register(self, stream_id: int, priority: int) -> Stream:
        stream = Stream(self, stream_id, priority, credit=self.config.send_window)
        self.streams[stream_id] = stream
        self.order.append(stream_id)
        self.counters.streams_opened += 1
        return stream

    # -- writing -------------------------------------------------------------

    def send(self, stream: Stream, data: bytes) -> Write:
        if (
            self.closed
            or stream.local_closed
            or stream.remote_closed
            or stream.id not in self.streams
        ):
            raise ClosedLink(f"stream {stream.id} is closed")
        ticket = Write(stream.id, len(data))
        if data:
            stream.outbox.append((bytearray(data), ticket))
        else:
            ticket.done = True
        return ticket

    # -- the radio slot ------------------------------------------------------

    def pump(self, max_bytes: int) -> int:
        budget = int(max_bytes)
        sent = 0
        while self.control and sent + len(self.control[0]) <= budget:
            frame = self.control.popleft()
            self.transport.write(frame)
            self.counters.frames_sent += 1
            sent += len(frame)
        while sent < budget:
            stream = self._most_urgent()
            if stream is None:
                break
            room = min(
                int(self.config.max_frame_size),
                int(stream.credit),
                budget - sent - HEADER_BYTES,
            )
            payload = stream.take(room) if room > 0 else b""
            if not payload:
                break
            frame = encode_frame(DATA, stream.id, payload)
            self.transport.write(frame)
            self.counters.frames_sent += 1
            self.counters.payload_bytes_sent += len(payload)
            stream.credit -= len(payload)
            sent += len(frame)
            self._rotate(stream)
        return sent

    def _most_urgent(self) -> Stream | None:
        """The stream with payload and room whose class is served first."""

        best: Stream | None = None
        for stream_id in self.order:
            stream = self.streams.get(stream_id)
            if stream is None or not stream.ready():
                continue
            if best is None or stream.priority > best.priority:
                best = stream
        return best

    def _rotate(self, stream: Stream) -> None:
        """Streams of one class take turns, so none of them owns the slot."""

        if stream.id in self.order:
            self.order.remove(stream.id)
            self.order.append(stream.id)

    # -- what the radio brings in --------------------------------------------

    def feed(self, data: bytes) -> None:
        frames, self._inbound = decode_frames(self._inbound + bytes(data))
        for frame in frames:
            self.counters.frames_received += 1
            if frame.command == OPEN:
                if frame.stream not in self.streams:
                    self.arrivals.append(self._register(frame.stream, PRIORITY_NORMAL))
            elif frame.command == DATA:
                self.counters.payload_bytes_received += len(frame.payload)
                stream = self.streams.get(frame.stream)
                if stream is not None:
                    stream.inbox += frame.payload
            elif frame.command == GRANT:
                stream = self.streams.get(frame.stream)
                if stream is not None:
                    stream.credit = min(
                        int(self.config.send_window),
                        stream.credit + grant_amount(frame.payload),
                    )
            elif frame.command == SHUT:
                stream = self.streams.get(frame.stream)
                if stream is not None:
                    stream.remote_closed = True
                    stream.settle(ClosedLink(f"the far end closed stream {stream.id}"))
                    self.retire(stream)

    def took(self, stream: Stream, amount: int) -> None:
        """Our consumer took bytes, so the far end gets that room back."""

        self.control.append(encode_frame(GRANT, stream.id, grant_payload(amount)))

    # -- closing -------------------------------------------------------------

    def shut(self, stream: Stream) -> None:
        """Stop writing on this stream; what has arrived is still there to read."""

        if stream.local_closed:
            return
        stream.local_closed = True
        stream.settle(ClosedLink(f"stream {stream.id} is closed"))
        self.control.append(encode_frame(SHUT, stream.id))
        self.retire(stream)

    def retire(self, stream: Stream) -> None:
        """A stream leaves the link once both ends are done and nothing is left."""

        if not stream.finished() or stream.id not in self.streams:
            return
        del self.streams[stream.id]
        if stream.id in self.order:
            self.order.remove(stream.id)
        self.counters.streams_closed += 1

    def close(self) -> None:
        """Shut the link down now, whatever the radio is doing."""

        if self.closed:
            return
        self.closed = True
        error = ClosedLink("the link is closed")
        for stream in list(self.streams.values()):
            stream.local_closed = True
            stream.settle(error)
            try:
                self.transport.write(encode_frame(SHUT, stream.id))
                self.counters.frames_sent += 1
            except LinkError:
                pass
            del self.streams[stream.id]
            self.counters.streams_closed += 1
        self.order.clear()
        self.control.clear()
        self.arrivals.clear()
