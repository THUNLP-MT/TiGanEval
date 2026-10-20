"""The station's end of the telemetry uplink.

Every conversation with a depot unit gets a stream id, every chunk handed to a
stream is tagged with that id, and the chunks go out on the radio most urgent
first, cut to the frame size the firmware takes so one upload cannot own a
whole slot.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from .protocol import (
    DATA, HEADER_BYTES, PRIORITY_NORMAL, LinkCounters, SessionConfig, Write,
    decode_frames, encode_frame,
)
from .streams import Stream


class Session:
    """One radio link, carrying several streams at once."""

    def __init__(self, transport: Any, config: SessionConfig | None = None):
        self.transport = transport
        self.config = config or SessionConfig()
        self.counters = LinkCounters()
        self.streams: dict[int, Stream] = {}
        self.queue: deque[tuple[int, int, bytes, Write]] = deque()
        self._next_id = 1
        self._inbound = b""

    def open_stream(self, priority: int = PRIORITY_NORMAL) -> Stream:
        stream = Stream(self, self._next_id, priority)
        self._next_id += 1
        self.streams[stream.id] = stream
        self.counters.streams_opened += 1
        return stream

    def accept_stream(self) -> Stream | None:
        return None

    def send(self, stream: Stream, data: bytes) -> Write:
        """Queue one run of payload, cut into frames, most urgent stream first."""

        ticket = Write(stream.id, len(data))
        size = int(self.config.max_frame_size)
        body = bytes(data)
        for start in range(0, len(body), size):
            self.queue.append(
                (stream.priority, stream.id, body[start : start + size], ticket)
            )
        self.counters.payload_bytes_sent += len(body)
        self.queue = deque(sorted(self.queue, key=lambda item: -item[0]))
        return ticket

    def pump(self, max_bytes: int) -> int:
        sent = payload_used = 0
        while self.queue:
            _priority, stream_id, data, _ticket = self.queue[0]
            frame = encode_frame(DATA, stream_id, data)
            if payload_used + len(data) > int(max_bytes):
                break
            self.queue.popleft()
            self.transport.write(frame)
            self.counters.frames_sent += 1
            sent += len(frame)
            payload_used += len(data)
        return sent

    def feed(self, data: bytes) -> None:
        frames, self._inbound = decode_frames(self._inbound + bytes(data))
        for frame in frames:
            self.counters.frames_received += 1
            self.counters.payload_bytes_received += HEADER_BYTES + len(frame.payload)
            stream = self.streams.get(frame.stream)
            if frame.command == DATA and stream is not None:
                stream.inbox += frame.payload

    def drop(self, stream: Stream) -> None:
        if self.streams.pop(stream.id, None) is not None:
            self.counters.streams_closed += 1

    def close(self) -> None:
        for stream in list(self.streams.values()):
            self.drop(stream)
        self.queue.clear()
