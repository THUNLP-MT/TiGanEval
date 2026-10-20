"""The broker channel used by the notification workers.

The three changes NOTIF-412 asks for, on top of the prototype: a notification
that fails three times goes to that queue's dead-letter queue instead of back
into the queue, a queue's `message_ttl` is treated as the maximum lifetime of
anything in it and nothing at that age is handed to a worker, and a queue with
a `max_length` stops growing once it is full.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    BrokerState,
    Clock,
    Message,
    QueueSpec,
    UnknownDeliveryTag,
)


class Channel:
    """One consumer channel over the shared broker state."""

    def __init__(self, state: BrokerState, clock: Clock):
        self.state = state
        self.clock = clock
        # How many times each message has failed so far.
        self.attempts: dict[str, int] = {}

    def declare(self, spec: QueueSpec) -> None:
        self.state.specs[spec.name] = spec.as_dict()
        self.state.queues.setdefault(spec.name, [])

    def publish(
        self,
        queues: Sequence[str],
        body: Any,
        headers: Mapping[str, Any] | None = None,
        ttl: float | None = None,
    ) -> list[str]:
        now = self.clock.now()
        published: list[str] = []
        for queue in queues:
            spec = self.state.spec(queue)
            lifetime = min(
                value for value in (ttl, spec.message_ttl) if value is not None
            ) if (ttl is not None or spec.message_ttl is not None) else None
            message = Message(
                id=self.state.new_message_id(),
                body=body,
                headers=dict(headers or {}),
                queue=str(queue),
                published_at=now,
                expires_at=None if lifetime is None else now + float(lifetime),
            )
            published.append(message.id)
            ready = self.state.ready(queue)
            if spec.max_length is not None and len(ready) >= int(spec.max_length):
                # The queue is full; stop it growing any further.
                continue
            ready.append(message)
        return published

    def get(self, queue: str) -> dict[str, Any] | None:
        ready = self.state.ready(queue)
        while ready:
            message = ready.pop(0)
            if self._expired(message):
                continue
            tag = self.state.new_delivery_tag()
            self.state.unacked[tag] = {"queue": str(queue), "message": message}
            return {"tag": tag, "message": message}
        return None

    def ack(self, tag: str) -> None:
        entry = self._take(tag)
        self.attempts.pop(str(entry["message"].id), None)
        self.state.settle(entry["message"], "acknowledged", queue=entry["queue"])

    def reject(self, tag: str, requeue: bool = False) -> None:
        entry = self._take(tag)
        queue = str(entry["queue"])
        message: Message = entry["message"]
        if not requeue:
            return
        spec = self.state.spec(queue)
        attempts = self.attempts.get(str(message.id), 0) + 1
        self.attempts[str(message.id)] = attempts
        if attempts >= int(spec.max_deliveries) and spec.dead_letter_queue is not None:
            self.state.ready(spec.dead_letter_queue).append(message)
            return
        self.state.ready(queue).insert(0, message)

    def drain_expired(self, queue: str) -> int:
        ready = self.state.ready(queue)
        survivors = [message for message in ready if not self._expired(message)]
        removed = len(ready) - len(survivors)
        ready[:] = survivors
        return removed

    def redelivery_count(self, tag: str) -> int:
        entry = self.state.unacked.get(str(tag))
        if entry is None:
            raise UnknownDeliveryTag(f"unknown delivery tag: {tag}")
        return self.attempts.get(str(entry["message"].id), 0)

    def _take(self, tag: str) -> dict[str, Any]:
        entry = self.state.unacked.pop(str(tag), None)
        if entry is None:
            raise UnknownDeliveryTag(f"unknown delivery tag: {tag}")
        return entry

    def _expired(self, message: Message) -> bool:
        deadline = message.expires_at
        return deadline is not None and float(deadline) <= self.clock.now()
