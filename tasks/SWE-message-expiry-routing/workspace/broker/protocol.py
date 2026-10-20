"""Runtime contract for the in-process notification broker.

Queue properties, message identity, the settlement ledger, the dead-letter
representation, and the clock below are the fixed part of the project: the
worker pool, the operator console, and the queue dashboard are all built
against them. Everything here is deterministic, and time moves only when the
operator moves it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


#: A copy of a message leaves the broker through exactly one of these.
DISPOSITIONS: tuple[str, ...] = ("acknowledged", "dead_lettered", "dropped")

#: Why a copy left a queue other than by acknowledgement.
REASONS: tuple[str, ...] = ("rejected", "expired", "maxlen")


class BrokerError(RuntimeError):
    pass


class UnknownQueue(BrokerError):
    pass


class UnknownDeliveryTag(BrokerError):
    pass


@dataclass(frozen=True, slots=True)
class QueueSpec:
    """The declared properties of one queue.

    ``dead_letter_queue``
        The queue named alongside this one to hold copies of its messages.
        ``None`` when this queue names none.
    ``message_ttl``
        How long, in seconds, a message published to this queue stays useful.
    ``max_length``
        How many messages may be waiting in this queue.
    ``max_deliveries``
        How many times one copy may be handed to a worker from this queue.
    """

    name: str
    dead_letter_queue: str | None = None
    message_ttl: float | None = None
    max_length: int | None = None
    max_deliveries: int = 3

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueueSpec":
        raw_ttl = value.get("message_ttl")
        raw_max = value.get("max_length")
        raw_dlq = value.get("dead_letter_queue")
        return cls(
            name=str(value["name"]),
            dead_letter_queue=None if raw_dlq is None else str(raw_dlq),
            message_ttl=None if raw_ttl is None else float(raw_ttl),
            max_length=None if raw_max is None else int(raw_max),
            max_deliveries=int(value.get("max_deliveries", 3)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dead_letter_queue": self.dead_letter_queue,
            "message_ttl": self.message_ttl,
            "max_length": self.max_length,
            "max_deliveries": self.max_deliveries,
        }


@dataclass(slots=True)
class Message:
    """One copy of a published payload living in one queue.

    ``published_at`` is when this copy entered the queue it is in and
    ``expires_at`` is the clock reading at which it stops being useful there;
    ``None`` means the copy has no deadline in this queue.
    """

    id: str
    body: Any
    headers: dict[str, Any] = field(default_factory=dict)
    queue: str = ""
    published_at: float = 0.0
    expires_at: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "body": deepcopy(self.body),
            "headers": deepcopy(self.headers),
            "queue": self.queue,
            "published_at": self.published_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Message":
        raw_expiry = value.get("expires_at")
        return cls(
            id=str(value["id"]),
            body=deepcopy(value.get("body")),
            headers=deepcopy(dict(value.get("headers", {}))),
            queue=str(value.get("queue", "")),
            published_at=float(value.get("published_at", 0.0)),
            expires_at=None if raw_expiry is None else float(raw_expiry),
        )


class Clock:
    """The operator-controlled clock. Nothing else observes real time."""

    def __init__(self, start: float = 0.0):
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def set(self, value: float) -> None:
        self._now = float(value)


class BrokerState:
    """Everything the broker keeps, and the snapshot it can be rebuilt from."""

    def __init__(self, snapshot: Mapping[str, Any] | None = None):
        source = dict(snapshot or {})
        self.specs: dict[str, dict[str, Any]] = {
            str(name): dict(spec) for name, spec in dict(source.get("specs", {})).items()
        }
        self.queues: dict[str, list[Message]] = {
            str(name): [Message.from_dict(item) for item in rows]
            for name, rows in dict(source.get("queues", {})).items()
        }
        self.unacked: dict[str, dict[str, Any]] = {
            str(tag): {
                "queue": str(entry.get("queue", "")),
                "message": Message.from_dict(entry["message"]),
            }
            for tag, entry in dict(source.get("unacked", {})).items()
        }
        self.settled: list[dict[str, Any]] = [
            dict(item) for item in source.get("settled", ())
        ]
        self.next_tag: int = int(source.get("next_tag", 1))
        self.next_message: int = int(source.get("next_message", 1))

    # -- identity -----------------------------------------------------
    def new_message_id(self) -> str:
        identifier = f"m-{self.next_message:05d}"
        self.next_message += 1
        return identifier

    def new_delivery_tag(self) -> str:
        tag = f"t-{self.next_tag:05d}"
        self.next_tag += 1
        return tag

    # -- settlement ---------------------------------------------------
    def settle(
        self,
        message: Message,
        disposition: str,
        *,
        reason: str | None = None,
        queue: str | None = None,
    ) -> None:
        """Append the ledger line the operator console shows for this copy.

        A line names the copy, the queue it is a line about, the disposition it
        left under and, where there is one, the reason.
        """

        if disposition not in DISPOSITIONS:
            raise BrokerError(f"unknown disposition: {disposition}")
        if reason is not None and reason not in REASONS:
            raise BrokerError(f"unknown reason: {reason}")
        self.settled.append(
            {
                "message_id": str(message.id),
                "disposition": str(disposition),
                "reason": None if reason is None else str(reason),
                "queue": str(queue if queue is not None else message.queue),
                "body": deepcopy(message.body),
                "headers": deepcopy(message.headers),
            }
        )

    # -- durability ---------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "specs": {name: dict(spec) for name, spec in self.specs.items()},
            "queues": {
                name: [message.as_dict() for message in messages]
                for name, messages in self.queues.items()
            },
            "unacked": {
                tag: {"queue": entry["queue"], "message": entry["message"].as_dict()}
                for tag, entry in self.unacked.items()
            },
            "settled": [dict(item) for item in self.settled],
            "next_tag": self.next_tag,
            "next_message": self.next_message,
        }

    def spec(self, queue: str) -> QueueSpec:
        name = str(queue)
        if name not in self.specs:
            raise UnknownQueue(f"queue {name!r} was never declared")
        return QueueSpec.from_mapping(self.specs[name])

    def ready(self, queue: str) -> list[Message]:
        name = str(queue)
        if name not in self.specs:
            raise UnknownQueue(f"queue {name!r} was never declared")
        return self.queues.setdefault(name, [])


#: The headers a message carries about its own history. ``x-death`` is the
#: ordered list of the queues it has left and why; the first-death fields
#: describe the event that first took it out of a queue.
DEATH_HISTORY_HEADER = "x-death"
FIRST_DEATH_QUEUE_HEADER = "x-first-death-queue"
FIRST_DEATH_REASON_HEADER = "x-first-death-reason"


def death_history(message: Message) -> list[dict[str, Any]]:
    """The history a message carries, oldest event first.

    One entry per (queue, reason) pair, holding the ``queue``, the ``reason``,
    the ``count`` of how many times that pair happened, and the ``time`` of the
    latest one.
    """

    history = message.headers.get(DEATH_HISTORY_HEADER)
    return [dict(item) for item in history] if isinstance(history, Sequence) else []


def first_death(message: Message) -> tuple[str | None, str | None]:
    """The queue and reason recorded for the first event in this history."""

    headers = dict(message.headers)
    queue = headers.get(FIRST_DEATH_QUEUE_HEADER)
    reason = headers.get(FIRST_DEATH_REASON_HEADER)
    return (
        None if queue is None else str(queue),
        None if reason is None else str(reason),
    )


def record_death(message: Message, queue: str, reason: str, now: float) -> None:
    """Write into the message's own headers that it left `queue` for `reason`.

    The history entry for that pair is created or its count raised, and the
    first-death fields are filled the first time and never rewritten.
    """

    if reason not in REASONS:
        raise BrokerError(f"unknown reason: {reason}")
    history = death_history(message)
    for entry in history:
        if str(entry.get("queue")) == str(queue) and str(entry.get("reason")) == str(reason):
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["time"] = float(now)
            break
    else:
        history.append(
            {
                "queue": str(queue),
                "reason": str(reason),
                "count": 1,
                "time": float(now),
            }
        )
    message.headers[DEATH_HISTORY_HEADER] = history
    message.headers.setdefault(FIRST_DEATH_QUEUE_HEADER, str(queue))
    message.headers.setdefault(FIRST_DEATH_REASON_HEADER, str(reason))


def redeliveries(message: Message, queue: str) -> int:
    """The rejections recorded for `queue` in this message's own history."""

    return sum(
        int(entry.get("count", 0))
        for entry in death_history(message)
        if str(entry.get("queue")) == str(queue)
        and str(entry.get("reason")) == "rejected"
    )


def dead_letter_copy(message: Message, target: QueueSpec, now: float) -> Message:
    """The copy of `message` that `target` would hold, as of `now`.

    It carries the same id, the same payload and the same history, with
    `target`'s name, `now` as its publication time, and the deadline
    `target`'s own properties give it.
    """

    ttl = target.message_ttl
    return Message(
        id=str(message.id),
        body=deepcopy(message.body),
        headers=deepcopy(dict(message.headers)),
        queue=str(target.name),
        published_at=float(now),
        expires_at=None if ttl is None else float(now) + float(ttl),
    )


__all__ = (
    "BrokerError",
    "BrokerState",
    "Clock",
    "DEATH_HISTORY_HEADER",
    "DISPOSITIONS",
    "FIRST_DEATH_QUEUE_HEADER",
    "FIRST_DEATH_REASON_HEADER",
    "Message",
    "QueueSpec",
    "REASONS",
    "UnknownDeliveryTag",
    "UnknownQueue",
    "dead_letter_copy",
    "death_history",
    "first_death",
    "record_death",
    "redeliveries",
)
