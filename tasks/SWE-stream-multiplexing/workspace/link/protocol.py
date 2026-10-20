"""The frame contract of the telemetry uplink.

One radio link carries every conversation the station has with a depot unit at
the same time, each conversation on its own stream id. The depot units run this
wire format in their firmware and are updated once a year by a technician with
a laptop, so this module ships with the firmware and is not ours to change:
what the station puts on the radio has to be what the firmware already reads.

The pieces below are the ones both ends agree on. `encode_frame` and
`decode_frames` are the codec; `OPEN`, `DATA`, `GRANT` and `SHUT` are the four
commands; `SessionConfig` is what the operator sets on a link; `LinkCounters`
is the nightly link report; `Write` is the ticket a writer holds while the link
owes it bytes; `ClosedLink` is what a closed link raises; `Transport` is the
radio; and `PeerEnd` is the depot unit's own end of the link, the same code
that runs in the firmware, so anything built here can be driven against it.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import Any, Mapping

#: The four commands the firmware understands.
OPEN, DATA, GRANT, SHUT = 1, 2, 3, 4
COMMAND_NAMES: Mapping[int, str] = {
    OPEN: "OPEN", DATA: "DATA", GRANT: "GRANT", SHUT: "SHUT",
}

#: Which end of a link a session is. The station is the ground side; the
#: device is the depot unit in the field.
STATION, DEVICE = "station", "device"

#: Service classes a stream may be opened with. A larger number is more urgent.
PRIORITY_BULK, PRIORITY_NORMAL, PRIORITY_HIGH = 0, 1, 2
PRIORITY_NAMES: Mapping[int, str] = {0: "bulk", 1: "normal", 2: "high"}

_HEADER = struct.Struct("!BIH")

#: Bytes of frame header in front of every payload.
HEADER_BYTES = _HEADER.size


class LinkError(RuntimeError):
    """Anything the link itself refuses to do."""


class ClosedLink(LinkError):
    """The stream or the session is closed and cannot carry this."""


class TransportRefused(LinkError):
    """The radio would not take the bytes it was handed."""


@dataclass(frozen=True, slots=True)
class Frame:
    """One unit on the radio: a command, the stream it belongs to, a payload."""

    command: int
    stream: int
    payload: bytes

    @property
    def name(self) -> str:
        return COMMAND_NAMES.get(int(self.command), f"command-{self.command}")


def encode_frame(command: int, stream: int, payload: bytes = b"") -> bytes:
    """One frame as the firmware reads it."""

    body = bytes(payload)
    if len(body) > 0xFFFF:
        raise LinkError("a frame payload cannot be longer than 65535 bytes")
    return _HEADER.pack(int(command), int(stream), len(body)) + body


def decode_frames(buffer: bytes) -> tuple[tuple[Frame, ...], bytes]:
    """Every whole frame in `buffer`, plus the bytes of the next one so far."""

    data = bytes(buffer)
    frames: list[Frame] = []
    offset = 0
    while len(data) - offset >= HEADER_BYTES:
        command, stream, size = _HEADER.unpack_from(data, offset)
        start = offset + HEADER_BYTES
        if len(data) - start < size:
            break
        frames.append(Frame(int(command), int(stream), data[start : start + size]))
        offset = start + size
    return tuple(frames), data[offset:]


def grant_payload(amount: int) -> bytes:
    """The payload of a GRANT frame: how many payload bytes it hands back."""

    return int(amount).to_bytes(4, "big")


def grant_amount(payload: bytes) -> int:
    """Read a GRANT frame's payload."""

    return int.from_bytes(bytes(payload)[:4].rjust(4, b"\0"), "big")


@dataclass(slots=True)
class SessionConfig:
    """What the operator sets on one link.

    `max_frame_size` is the largest payload the firmware's frame buffer takes.
    `send_window` is how many payload bytes of one stream a depot unit can hold
    for us before its own consumer has taken them; the unit has that much
    memory per stream and nothing more. `recv_window` is the same number in the
    other direction, for what the station holds on the unit's behalf.
    """

    side: str = STATION
    max_frame_size: int = 256
    send_window: int = 1024
    recv_window: int = 1024


#: The six numbers the nightly link report is built from.
COUNTER_FIELDS = (
    "streams_opened",
    "streams_closed",
    "frames_sent",
    "frames_received",
    "payload_bytes_sent",
    "payload_bytes_received",
)


@dataclass(slots=True)
class LinkCounters:
    """The nightly link report for one session.

    The depot bills the station on `payload_bytes_sent` and
    `payload_bytes_received`; the radio operator reads `frames_sent` and
    `frames_received` against the slots we were given. A stream is counted once
    in `streams_opened`, whichever end opened it, and once in `streams_closed`
    when it leaves the link, so opened minus closed is what is still up.
    """

    streams_opened: int = 0
    streams_closed: int = 0
    frames_sent: int = 0
    frames_received: int = 0
    payload_bytes_sent: int = 0
    payload_bytes_received: int = 0

    def snapshot(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in COUNTER_FIELDS}

    def copy(self) -> "LinkCounters":
        return LinkCounters(**self.snapshot())

    def reset(self) -> None:
        for name in COUNTER_FIELDS:
            setattr(self, name, 0)


@dataclass(slots=True)
class Write:
    """The ticket a writer holds while the link owes it bytes.

    `total` is what was handed over, `delivered` is what has gone out on the
    radio so far, `done` marks the ticket finished and `error` carries whatever
    finished it when something other than delivery did.
    """

    stream: int
    total: int
    delivered: int = 0
    done: bool = False
    error: BaseException | None = None

    @property
    def owed(self) -> int:
        return max(0, int(self.total) - int(self.delivered))


class Transport:
    """The radio. `write` takes bytes when there is a slot and refuses when not."""

    def __init__(self, refusing: bool = False):
        self.taken = bytearray()
        self.calls: list[int] = []
        self.refusing = bool(refusing)

    def write(self, data: bytes) -> int:
        if self.refusing:
            raise TransportRefused("the radio is not taking bytes")
        block = bytes(data)
        self.taken += block
        self.calls.append(len(block))
        return len(block)


class PeerEnd:
    """The depot unit's end of the link, as the firmware implements it.

    It decodes what the station sends, delivers payload into one buffer per
    stream, opens streams of its own on even ids, hands back a GRANT whenever
    its consumer takes bytes, and writes down anything it could not use in
    `rejected_frames`. It schedules nothing: what goes out of the station is
    the station's business.
    """

    def __init__(self, config: SessionConfig):
        self.config = config
        self.received: dict[int, bytearray] = {}
        self.held: dict[int, int] = {}
        self.taken: dict[int, int] = {}
        self.mine: list[int] = []
        self.theirs: list[int] = []
        self.shut_seen: list[int] = []
        self.rejected_frames: list[dict[str, Any]] = []
        self.frames_seen = 0
        self.payload_seen = 0
        self.grants_sent = 0
        self.outbox = bytearray()
        self._rest = b""
        self._next_id = 2

    # -- what the station sends it -----------------------------------------

    def feed(self, data: bytes) -> tuple[Frame, ...]:
        frames, self._rest = decode_frames(self._rest + bytes(data))
        for frame in frames:
            self.frames_seen += 1
            self._accept(frame)
        return frames

    def _reject(self, frame: Frame, reason: str) -> None:
        self.rejected_frames.append(
            {
                "reason": reason,
                "command": frame.name,
                "stream": int(frame.stream),
                "payload_bytes": len(frame.payload),
                "at": self.frames_seen,
            }
        )

    def _accept(self, frame: Frame) -> None:
        if frame.command not in COMMAND_NAMES:
            self._reject(frame, "a command byte the firmware does not have")
            return
        if len(frame.payload) > self.config.max_frame_size:
            self._reject(frame, "a payload longer than the frame buffer")
            return
        if frame.command == OPEN:
            if frame.stream in self.received:
                self._reject(frame, "a stream id this end is already using")
                return
            self.received[frame.stream] = bytearray()
            self.held[frame.stream] = 0
            self.taken[frame.stream] = 0
            self.theirs.append(int(frame.stream))
            return
        if frame.stream not in self.received:
            self._reject(frame, "a stream the station never opened")
            return
        if frame.command == DATA:
            self.received[frame.stream] += frame.payload
            self.held[frame.stream] += len(frame.payload)
            self.payload_seen += len(frame.payload)
        elif frame.command == SHUT:
            self.shut_seen.append(int(frame.stream))

    # -- what it sends the station -----------------------------------------

    def open_stream(self) -> int:
        stream = self._next_id
        self._next_id += 2
        self.received[stream] = bytearray()
        self.held[stream] = 0
        self.taken[stream] = 0
        self.mine.append(stream)
        self.outbox += encode_frame(OPEN, stream)
        return stream

    def push(self, stream: int, payload: bytes) -> int:
        body = bytes(payload)
        size = int(self.config.max_frame_size)
        for start in range(0, len(body), size):
            self.outbox += encode_frame(DATA, stream, body[start : start + size])
        return len(body)

    def drain(self, stream: int, amount: int) -> int:
        """Its consumer takes bytes, and the room they were in is handed back."""

        taken = min(int(amount), int(self.held.get(stream, 0)))
        if taken <= 0:
            return 0
        self.held[stream] -= taken
        self.taken[stream] = self.taken.get(stream, 0) + taken
        self.grants_sent += 1
        self.outbox += encode_frame(GRANT, stream, grant_payload(taken))
        return taken

    def close_stream(self, stream: int) -> None:
        self.outbox += encode_frame(SHUT, int(stream))

    def outbound(self) -> bytes:
        block = bytes(self.outbox)
        self.outbox.clear()
        return block

    # -- what an operator reads off it -------------------------------------

    def digest(self, stream: int) -> str:
        return hashlib.sha256(bytes(self.received.get(stream, b""))).hexdigest()[:16]

    def arrived(self, stream: int) -> int:
        return len(self.received.get(stream, b""))


def digest_of(payload: bytes) -> str:
    """The short digest the link report prints for a run of payload."""

    return hashlib.sha256(bytes(payload)).hexdigest()[:16]


__all__ = (
    "COMMAND_NAMES", "COUNTER_FIELDS", "DATA", "DEVICE", "Frame", "GRANT",
    "HEADER_BYTES", "LinkCounters", "LinkError", "ClosedLink", "OPEN",
    "PRIORITY_BULK", "PRIORITY_HIGH", "PRIORITY_NAMES", "PRIORITY_NORMAL",
    "PeerEnd", "SHUT", "STATION", "SessionConfig", "Transport",
    "TransportRefused", "Write", "decode_frames", "digest_of", "encode_frame",
    "grant_amount", "grant_payload",
)
