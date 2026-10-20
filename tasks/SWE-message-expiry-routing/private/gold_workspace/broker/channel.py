"""The broker channel used by the notification workers."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    BrokerState,
    Clock,
    Message,
    QueueSpec,
    UnknownDeliveryTag,
    dead_letter_copy,
    record_death,
    redeliveries,
)


class Channel:
    """One consumer channel over the shared broker state."""

    def __init__(self, state: BrokerState, clock: Clock):
        self.state = state
        self.clock = clock

    # -- declaration --------------------------------------------------
    def declare(self, spec: QueueSpec) -> None:
        self.state.specs[spec.name] = spec.as_dict()
        self.state.queues.setdefault(spec.name, [])

    # -- publication --------------------------------------------------
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
            lifetime = ttl if ttl is not None else spec.message_ttl
            message = Message(
                id=self.state.new_message_id(),
                body=body,
                headers=dict(headers or {}),
                queue=str(queue),
                published_at=now,
                expires_at=None if lifetime is None else now + float(lifetime),
            )
            self.state.ready(queue).append(message)
            self._enforce_length(queue)
            published.append(message.id)
        return published

    # -- consumption --------------------------------------------------
    def get(self, queue: str) -> dict[str, Any] | None:
        ready = self.state.ready(queue)
        while ready:
            message = ready.pop(0)
            if self._is_expired(message):
                self._dead_letter(message, queue, "expired")
                continue
            tag = self.state.new_delivery_tag()
            self.state.unacked[tag] = {"queue": str(queue), "message": message}
            return {"tag": tag, "message": message}
        return None

    def ack(self, tag: str) -> None:
        entry = self._take(tag)
        self.state.settle(entry["message"], "acknowledged", queue=entry["queue"])

    def reject(self, tag: str, requeue: bool = False) -> None:
        entry = self._take(tag)
        queue = str(entry["queue"])
        message: Message = entry["message"]
        if not requeue:
            self._dead_letter(message, queue, "rejected")
            return
        spec = self.state.spec(queue)
        if redeliveries(message, queue) + 1 >= int(spec.max_deliveries):
            self._dead_letter(message, queue, "rejected")
            return
        record_death(message, queue, "rejected", self.clock.now())
        self.state.ready(queue).insert(0, message)
        self._enforce_length(queue)

    def drain_expired(self, queue: str) -> int:
        ready = self.state.ready(queue)
        survivors: list[Message] = []
        expired: list[Message] = []
        for message in ready:
            (expired if self._is_expired(message) else survivors).append(message)
        ready[:] = survivors
        for message in expired:
            self._dead_letter(message, queue, "expired")
        return len(expired)

    def redelivery_count(self, tag: str) -> int:
        entry = self.state.unacked.get(str(tag))
        if entry is None:
            raise UnknownDeliveryTag(f"unknown delivery tag: {tag}")
        return redeliveries(entry["message"], str(entry["queue"]))

    # -- internals ----------------------------------------------------
    def _take(self, tag: str) -> dict[str, Any]:
        entry = self.state.unacked.pop(str(tag), None)
        if entry is None:
            raise UnknownDeliveryTag(f"unknown delivery tag: {tag}")
        return entry

    def _is_expired(self, message: Message) -> bool:
        deadline = message.expires_at
        return deadline is not None and float(deadline) <= self.clock.now()

    @staticmethod
    def _longest_waiting(ready: Sequence[Message]) -> int:
        """Where the copy that has been waiting in this queue longest sits.

        Arrivals append, so this is the front of the queue until a rejection
        puts a copy back there: the copy at the front is then the one that has
        waited least.
        """

        return min(range(len(ready)), key=lambda index: ready[index].published_at)

    def _enforce_length(self, queue: str) -> None:
        spec = self.state.spec(queue)
        if spec.max_length is None:
            return
        ready = self.state.ready(queue)
        while len(ready) > int(spec.max_length):
            self._dead_letter(ready.pop(self._longest_waiting(ready)), queue, "maxlen")

    def _dead_letter(self, message: Message, queue: str, reason: str) -> None:
        now = self.clock.now()
        record_death(message, queue, reason, now)
        target = self.state.spec(queue).dead_letter_queue
        if target is None or target not in self.state.specs:
            self.state.settle(message, "dropped", reason=reason, queue=queue)
            return
        self.state.settle(message, "dead_lettered", reason=reason, queue=queue)
        self.state.ready(target).append(
            dead_letter_copy(message, self.state.spec(target), now)
        )
        self._enforce_length(target)
