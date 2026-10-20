"""One stream on the uplink: what it is carrying and where it is going."""

from __future__ import annotations

from typing import Any

from .protocol import PRIORITY_NORMAL, Write


class Stream:
    """One conversation with a depot unit, on its own stream id."""

    def __init__(self, session: Any, stream_id: int, priority: int = PRIORITY_NORMAL):
        self.session = session
        self.id = int(stream_id)
        self.priority = int(priority)
        self.inbox = bytearray()

    def write(self, data: bytes) -> Write:
        return self.session.send(self, bytes(data))

    def read(self, size: int | None = None) -> bytes:
        block = bytes(self.inbox) if size is None else bytes(self.inbox[: int(size)])
        del self.inbox[: len(block)]
        return block

    def close(self) -> None:
        self.session.drop(self)
