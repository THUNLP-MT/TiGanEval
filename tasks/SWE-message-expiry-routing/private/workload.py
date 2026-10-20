'Deterministic queue topologies and broker programs.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


MAX_DELIVERIES = 3
FEED_MAX_LENGTH = 3
ALERT_TTL_SECONDS = 30.0
SLOW_ALERT_TTL_SECONDS = 300.0


DIGEST_TTL_SECONDS = 20.0
HOLDING_MAX_LENGTH = 2
SHARED_MAX_DELIVERIES = 2


NIGHTLY_DIGEST_TTL_SECONDS = 45.0
NIGHTLY_DIGEST_WAIT_SECONDS = 25.0


DIGEST_HANDBACK_GAP_SECONDS = 5.0


def holding_queue_names(seed: int, scale: int) -> tuple[str, str, str]:
    'The source, peer and shared-target names for one holding program.'

    if scale <= 1:
        return "digest", "receipts", "holding"
    stem = f"route-{int(seed):x}"
    return f"{stem}-alpha", f"{stem}-beta", f"{stem}-gamma"


def _spec(
    name: str,
    *,
    dead_letter_queue: str | None = None,
    message_ttl: float | None = None,
    max_length: int | None = None,
    max_deliveries: int = MAX_DELIVERIES,
) -> dict[str, Any]:
    return {
        "name": name,
        "dead_letter_queue": dead_letter_queue,
        "message_ttl": message_ttl,
        "max_length": max_length,
        "max_deliveries": max_deliveries,
    }


def _body(batch: int, tag: str) -> dict[str, Any]:
    return {"tag": tag, "batch": batch, "payload": f"{tag}-{batch:03d}"}


def _poison(seed: int, scale: int) -> list[dict[str, Any]]:
    return [
        {"type": "reset", "now": 0.0},
        {
            "type": "declare",
            "label": "declare-work",
            "specs": [
                _spec("work", dead_letter_queue="work.dead"),
                _spec("work.dead"),
            ],
        },
        {"type": "publish", "label": "pub-a", "queues": ["work"], "body": _body(seed, "a")},
        {"type": "publish", "label": "pub-b", "queues": ["work"], "body": _body(seed, "b")},
        {"type": "publish", "label": "pub-c", "queues": ["work"], "body": _body(seed, "c")},
        {"type": "get", "label": "take-1", "queue": "work"},
        {"type": "reject", "label": "reject-1", "tag_of": "take-1", "requeue": True},
        {"type": "get", "label": "take-2", "queue": "work"},
        {"type": "reject", "label": "reject-2", "tag_of": "take-2", "requeue": True},
        {"type": "get", "label": "take-3", "queue": "work"},
        {"type": "reject", "label": "reject-3", "tag_of": "take-3", "requeue": True},
        {"type": "get", "label": "take-4", "queue": "work"},
        {"type": "ack", "label": "ack-4", "tag_of": "take-4"},
        {"type": "get", "label": "take-5", "queue": "work"},
        {"type": "reject", "label": "reject-5", "tag_of": "take-5", "requeue": False},
        {"type": "get", "label": "take-6", "queue": "work"},
        {"type": "get", "label": "take-dead-1", "queue": "work.dead"},
        {"type": "ack", "label": "ack-dead-1", "tag_of": "take-dead-1"},
        {"type": "inspect", "label": "poison-final"},
    ]


def _ttl(seed: int, scale: int) -> list[dict[str, Any]]:
    return [
        {"type": "reset", "now": 0.0},
        {
            "type": "declare",
            "label": "declare-alerts",
            "specs": [
                _spec("alerts", dead_letter_queue="alerts.dead", message_ttl=ALERT_TTL_SECONDS),
                _spec(
                    "alerts.slow",
                    dead_letter_queue="alerts.dead",
                    message_ttl=SLOW_ALERT_TTL_SECONDS,
                ),
                _spec("alerts.dead"),
            ],
        },
        {
            "type": "publish",
            "label": "pub-short",
            "queues": ["alerts"],
            "body": _body(seed, "short"),
            "ttl": 5.0,
        },
        {
            "type": "publish",
            "label": "pub-fanout",
            "queues": ["alerts", "alerts.slow"],
            "body": _body(seed, "fanout"),
        },
        {"type": "advance", "label": "advance-10", "seconds": 10.0},
        {"type": "get", "label": "take-alert", "queue": "alerts"},
        {"type": "ack", "label": "ack-alert", "tag_of": "take-alert"},
        {"type": "advance", "label": "advance-25", "seconds": 25.0},
        {"type": "publish", "label": "pub-late", "queues": ["alerts"], "body": _body(seed, "late")},
        {"type": "drain_expired", "label": "drain-fresh", "queue": "alerts"},
        {"type": "advance", "label": "advance-40", "seconds": 40.0},
        {"type": "drain_expired", "label": "drain-stale", "queue": "alerts"},
        {"type": "get", "label": "take-slow", "queue": "alerts.slow"},
        {"type": "ack", "label": "ack-slow", "tag_of": "take-slow"},
        {"type": "inspect", "label": "ttl-final"},
    ]


def _overflow(seed: int, scale: int) -> list[dict[str, Any]]:
    if scale == 1:


        return [
            {"type": "reset", "now": 0.0},
            {
                "type": "declare",
                "label": "declare-feed",
                "specs": [
                    _spec("feed", dead_letter_queue="feed.dead", max_length=FEED_MAX_LENGTH),
                    _spec("feed.dead"),
                    _spec("side"),
                ],
            },
            {
                "type": "publish",
                "label": "pub-side",
                "queues": ["side"],
                "body": _body(seed, "side"),
            },
            {
                "type": "publish",
                "label": "pub-p1",
                "queues": ["feed"],
                "body": _body(seed, "p1"),
            },
            {"type": "advance", "label": "clock-1", "seconds": 1.0},
            {
                "type": "publish",
                "label": "pub-p2",
                "queues": ["feed"],
                "body": _body(seed, "p2"),
            },
            {"type": "advance", "label": "clock-2", "seconds": 1.0},
            {
                "type": "publish",
                "label": "pub-p3",
                "queues": ["feed"],
                "body": _body(seed, "p3"),
            },
            {"type": "get", "label": "take-feed-1", "queue": "feed"},
            {"type": "get", "label": "take-feed-2", "queue": "feed"},
            {"type": "advance", "label": "clock-3", "seconds": 1.0},
            {
                "type": "publish",
                "label": "pub-p4",
                "queues": ["feed"],
                "body": _body(seed, "p4"),
            },
            {"type": "get", "label": "take-feed-3", "queue": "feed"},
            {
                "type": "reject",
                "label": "reject-feed-1",
                "tag_of": "take-feed-1",
                "requeue": True,
            },
            {
                "type": "reject",
                "label": "reject-feed-2",
                "tag_of": "take-feed-2",
                "requeue": True,
            },
            {"type": "advance", "label": "clock-4", "seconds": 1.0},
            {
                "type": "publish",
                "label": "pub-p5",
                "queues": ["feed"],
                "body": _body(seed, "p5"),
            },
            {"type": "inspect", "label": "overflow-final"},
        ]

    events: list[dict[str, Any]] = [
        {"type": "reset", "now": 0.0},
        {
            "type": "declare",
            "label": "declare-feed",
            "specs": [
                _spec("feed", dead_letter_queue="feed.dead", max_length=FEED_MAX_LENGTH),
                _spec("feed.dead"),
                _spec("side"),
            ],
        },
        {"type": "publish", "label": "pub-side", "queues": ["side"], "body": _body(seed, "side")},
    ]
    for index in range(1, 6):
        events.append(
            {
                "type": "publish",
                "label": f"pub-p{index}",
                "queues": ["feed"],
                "body": _body(seed, f"p{index}"),
            }
        )
    events.append({"type": "get", "label": "take-feed", "queue": "feed"})
    for index in range(6, 8):
        events.append(
            {
                "type": "publish",
                "label": f"pub-p{index}",
                "queues": ["feed"],
                "body": _body(seed, f"p{index}"),
            }
        )
    events.append({"type": "inspect", "label": "overflow-final"})
    return events


def _restart(seed: int, scale: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {"type": "reset", "now": 0.0},
        {
            "type": "declare",
            "label": "declare-orders",
            "specs": [
                _spec("orders", dead_letter_queue="orders.dead"),
                _spec("orders.dead"),
            ],
        },
        {"type": "publish", "label": "pub-a", "queues": ["orders"], "body": _body(seed, "a")},
        {"type": "get", "label": "take-a", "queue": "orders"},
        {"type": "ack", "label": "ack-a", "tag_of": "take-a"},
        {"type": "publish", "label": "pub-b", "queues": ["orders"], "body": _body(seed, "b")},
        {"type": "get", "label": "take-b", "queue": "orders"},
        {"type": "reject", "label": "reject-b", "tag_of": "take-b", "requeue": False},
        {"type": "publish", "label": "pub-c", "queues": ["orders"], "body": _body(seed, "c")},
        {"type": "get", "label": "take-c1", "queue": "orders"},
        {"type": "reject", "label": "reject-c1", "tag_of": "take-c1", "requeue": True},
        {"type": "get", "label": "take-c2", "queue": "orders"},
        {"type": "reject", "label": "reject-c2", "tag_of": "take-c2", "requeue": True},
        {"type": "publish", "label": "pub-d", "queues": ["orders"], "body": _body(seed, "d")},
    ]
    if scale > 1:


        events.extend(
            [
                {"type": "get", "label": "take-c3", "queue": "orders"},
                {"type": "inspect", "label": "before-restart"},
                {"type": "restart", "label": "restart"},
                {"type": "inspect", "label": "after-restart"},
                {
                    "type": "reject",
                    "label": "reject-c3",
                    "tag_of": "take-c3",
                    "requeue": True,
                },
                {"type": "get", "label": "take-d", "queue": "orders"},
                {"type": "inspect", "label": "restart-final"},
            ]
        )
    else:

        events.extend(
            [
                {"type": "inspect", "label": "before-restart"},
                {"type": "restart", "label": "restart"},
                {"type": "inspect", "label": "after-restart"},
                {"type": "get", "label": "take-c3", "queue": "orders"},
                {
                    "type": "reject",
                    "label": "reject-c3",
                    "tag_of": "take-c3",
                    "requeue": True,
                },
                {"type": "get", "label": "take-d", "queue": "orders"},
                {"type": "inspect", "label": "restart-final"},
            ]
        )
    return events


def _holding(seed: int, scale: int) -> list[dict[str, Any]]:
    "Two teams' queues behind one capped holding queue."

    digest, receipts, holding = holding_queue_names(seed, scale)
    events: list[dict[str, Any]] = [
        {"type": "reset", "now": 0.0},
        {
            "type": "declare",
            "label": "declare-holding",
            "specs": [
                _spec(
                    digest,
                    dead_letter_queue=holding,
                    message_ttl=DIGEST_TTL_SECONDS,
                    max_length=HOLDING_MAX_LENGTH,
                    max_deliveries=SHARED_MAX_DELIVERIES,
                ),
                _spec(
                    receipts,
                    dead_letter_queue=holding,
                    max_deliveries=SHARED_MAX_DELIVERIES,
                ),
                _spec(
                    holding,
                    max_length=HOLDING_MAX_LENGTH,
                    max_deliveries=SHARED_MAX_DELIVERIES,
                ),
            ],
        },
        {"type": "publish", "label": "pub-d1", "queues": [digest], "body": _body(seed, "d1")},
        {"type": "publish", "label": "pub-d2", "queues": [digest], "body": _body(seed, "d2")},
        {"type": "publish", "label": "pub-d3", "queues": [digest], "body": _body(seed, "d3")},
        {"type": "publish", "label": "pub-r1", "queues": [receipts], "body": _body(seed, "r1")},
        {"type": "publish", "label": "pub-r2", "queues": [receipts], "body": _body(seed, "r2")},
        {"type": "get", "label": "take-r1", "queue": receipts},
        {"type": "reject", "label": "reject-r1", "tag_of": "take-r1", "requeue": True},
    ]
    if scale > 1:
        events.append({"type": "restart", "label": "deploy"})
    events.extend(
        [
            {"type": "get", "label": "take-r2", "queue": receipts},
            {"type": "reject", "label": "reject-r2", "tag_of": "take-r2", "requeue": True},
            {"type": "get", "label": "take-hold", "queue": holding},
            {"type": "ack", "label": "ack-hold", "tag_of": "take-hold"},
        ]
    )
    if scale > 1:
        events.extend(
            [
                {
                    "type": "advance",
                    "label": "advance-to-deadline",
                    "seconds": DIGEST_TTL_SECONDS,
                },
                {"type": "get", "label": "take-stale", "queue": digest},
                {"type": "drain_expired", "label": "drain-digest", "queue": digest},
                {
                    "type": "publish",
                    "label": "pub-nightly",
                    "queues": [digest],
                    "body": _body(seed, "nightly"),
                    "ttl": NIGHTLY_DIGEST_TTL_SECONDS,
                },
                {
                    "type": "advance",
                    "label": "advance-past-queue-lifetime",
                    "seconds": NIGHTLY_DIGEST_WAIT_SECONDS,
                },
                {"type": "get", "label": "take-nightly", "queue": digest},
                {"type": "ack", "label": "ack-nightly", "tag_of": "take-nightly"},
            ]
        )
    events.extend(
        [
            {"type": "get", "label": "take-r3", "queue": receipts},
            {"type": "ack", "label": "ack-r3", "tag_of": "take-r3"},
        ]
    )
    if scale > 1:
        events.extend(
            [
                {
                    "type": "publish",
                    "label": "pub-e1",
                    "queues": [digest],
                    "body": _body(seed, "e1"),
                },
                {
                    "type": "advance",
                    "label": "advance-between-digests",
                    "seconds": DIGEST_HANDBACK_GAP_SECONDS,
                },
                {
                    "type": "publish",
                    "label": "pub-e2",
                    "queues": [digest],
                    "body": _body(seed, "e2"),
                },
                {"type": "get", "label": "take-e1", "queue": digest},
                {"type": "get", "label": "take-e2", "queue": digest},
                {
                    "type": "advance",
                    "label": "advance-before-handback",
                    "seconds": DIGEST_HANDBACK_GAP_SECONDS,
                },
                {
                    "type": "publish",
                    "label": "pub-e3",
                    "queues": [digest],
                    "body": _body(seed, "e3"),
                },
                {"type": "reject", "label": "reject-e1", "tag_of": "take-e1", "requeue": True},
                {"type": "reject", "label": "reject-e2", "tag_of": "take-e2", "requeue": True},
            ]
        )
    events.append({"type": "inspect", "label": "holding-final"})
    return events


def _campaign(seed: int, scale: int) -> list[dict[str, Any]]:
    'A release-only queue whose name and cap do not occur in any record.'

    queue = f"campaign-{seed}"
    dead = f"{queue}.dead"
    events: list[dict[str, Any]] = [
        {"type": "reset", "now": 0.0},
        {
            "type": "declare",
            "label": "declare-campaign",
            "specs": [
                _spec(queue, dead_letter_queue=dead, max_length=4),
                _spec(dead),
            ],
        },
    ]
    for index in range(1, 6):
        events.append(
            {
                "type": "publish",
                "label": f"pub-campaign-{index}",
                "queues": [queue],
                "body": _body(seed, f"campaign-{index}"),
            }
        )
    events.append({"type": "inspect", "label": "campaign-final"})
    return events


PHASE_BUILDERS = {
    "poison": _poison,
    "ttl": _ttl,
    "overflow": _overflow,
    "restart": _restart,
    "holding": _holding,
    "campaign": _campaign,
}


RELEASE_PHASES: tuple[str, ...] = (
    "poison",
    "ttl",
    "overflow",
    "restart",
    "holding",
    "campaign",
)


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    if profile == "release":
        program: list[dict[str, Any]] = []
        for phase in RELEASE_PHASES:


            phase_scale = 1 if phase == "overflow" else scale
            for event in PHASE_BUILDERS[phase](seed, phase_scale):
                program.append({**event, "phase": phase})
        return program
    builder = PHASE_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown broker program profile: {profile}")
    return [{**event, "phase": profile} for event in builder(seed, scale)]


def queue_specs(program: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for event in program:
        if str(event.get("type")) == "declare":
            for spec in event.get("specs", ()):
                specs[str(spec["name"])] = dict(spec)
    return specs
