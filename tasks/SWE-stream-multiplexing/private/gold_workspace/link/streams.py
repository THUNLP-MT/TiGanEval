"""One stream on the uplink: what it is carrying and where it is going.

A stream holds the payload it still owes the radio together with the ticket
each run of payload was handed over on, what has arrived for it and has not
been read yet, how much room the depot unit still has for it, and the two
halves of its close.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from .protocol import ClosedLink, PRIORITY_NORMAL, Write


class Stream:
    """One conversation with a depot unit, on its own stream id."""

    def __init__(
        self,
        session: Any,
        stream_id: int,
        priority: int = PRIORITY_NORMAL,
        credit: int = 0,
    ):
        self.session = session
        self.id = int(stream_id)
        self.priority = int(priority)
        self.credit = int(credit)
        self.outbox: deque[tuple[bytearray, Write]] = deque()
        self.inbox = bytearray()
        self.local_closed = False
        self.remote_closed = False

    # -- what a caller does with it ------------------------------------------

    def write(self, data: bytes) -> Write:
        return self.session.send(self, bytes(data))

    def read(self, size: int | None = None) -> bytes:
        """What has arrived and not been read, closed or not."""

        if self.session.closed:
            raise ClosedLink(f"the link carrying stream {self.id} is closed")
        block = bytes(self.inbox) if size is None else bytes(self.inbox[: int(size)])
        del self.inbox[: len(block)]
        if block:
            self.session.took(self, len(block))
        self.session.retire(self)
        return block

    def close(self) -> None:
        self.session.shut(self)

    # -- what the session does with it ---------------------------------------

    @property
    def owed(self) -> int:
        return sum(len(block) for block, _ in self.outbox)

    def ready(self) -> bool:
        """Has payload waiting and room at the far end to put it in."""

        return bool(self.outbox) and self.credit > 0

    def take(self, limit: int) -> bytes:
        """The next `limit` payload bytes this stream owes, tickets advanced."""

        out = bytearray()
        while self.outbox and len(out) < limit:
            block, ticket = self.outbox[0]
            chunk = bytes(block[: limit - len(out)])
            del block[: len(chunk)]
            out += chunk
            ticket.delivered += len(chunk)
            if not block:
                self.outbox.popleft()
                ticket.done = True
        return bytes(out)

    def settle(self, error: BaseException) -> list[Write]:
        """Finish every ticket still waiting on this stream, and say why."""

        released: list[Write] = []
        while self.outbox:
            _block, ticket = self.outbox.popleft()
            ticket.done = True
            ticket.error = error
            released.append(ticket)
        return released

    def finished(self) -> bool:
        return self.local_closed and self.remote_closed and not self.inbox
