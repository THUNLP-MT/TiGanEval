"""The broker channel used by the notification workers.

The current channel publishes, hands messages out one at a time, and puts a
rejected message back so another worker can try it.
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
        published: list[str] = []
        for queue in queues:
            message = Message(
                id=self.state.new_message_id(),
                body=body,
                headers=dict(headers or {}),
                queue=str(queue),
                published_at=self.clock.now(),
            )
            self.state.ready(queue).append(message)
            published.append(message.id)
        return published

    def get(self, queue: str) -> dict[str, Any] | None:
        ready = self.state.ready(queue)
        if not ready:
            return None
        message = ready.pop(0)
        tag = self.state.new_delivery_tag()
        self.state.unacked[tag] = {"queue": str(queue), "message": message}
        return {"tag": tag, "message": message}

    def ack(self, tag: str) -> None:
        entry = self.state.unacked.pop(str(tag), None)
        if entry is None:
            raise UnknownDeliveryTag(f"unknown delivery tag: {tag}")
        self.state.settle(entry["message"], "acknowledged", queue=entry["queue"])

    def reject(self, tag: str, requeue: bool = False) -> None:
        entry = self.state.unacked.pop(str(tag), None)
        if entry is None:
            raise UnknownDeliveryTag(f"unknown delivery tag: {tag}")
        if requeue:
            self.state.ready(entry["queue"]).insert(0, entry["message"])

    def drain_expired(self, queue: str) -> int:
        return 0

    def redelivery_count(self, tag: str) -> int:
        return 0
