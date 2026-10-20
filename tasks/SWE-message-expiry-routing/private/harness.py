'Deterministic, sandboxed analysis of one broker workspace.'

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import RELEASE_PHASES, build_program, queue_specs


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("broker/channel.py", "broker/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-broker-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "seed": 33, "scale": 2}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "poison-message-drill": {"profile": "poison", "seed": 2, "scale": 1},
    "expiry-sweep": {"profile": "ttl", "seed": 8, "scale": 1},
    "overflow-burst": {"profile": "overflow", "seed": 14, "scale": 1},
    "broker-restart-drill": {"profile": "restart", "seed": 20, "scale": 1},
    "shared-holding-drill": {"profile": "holding", "seed": 26, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "accounted_message_disposition": "disposition_failures",
    "bounded_redelivery": "redelivery_failures",
    "publication_time_expiry": "expiry_failures",
    "bounded_queue_overflow": "overflow_failures",
    "restart_durable_broker_state": "restart_failures",
}
PHASES = RELEASE_PHASES


_PROVENANCE_DETAIL = "the copy does not show why it moved or which queue it came from"


_PROVENANCE_GAP = {
    "ledger": "has a line in the console that does not say what took it out",
    "history": "arrived carrying no history of the queue it came from or what took it out",
    "event": "arrived carrying history that does not include the move shown in the console",
    "count": "arrived carrying a rejection total that disagrees with the handouts",
    "summary": "arrived with a summary line that disagrees with its own history",
}

_CACHE = AnalysisCache()


def _invoke_program(
    artifact_dir: Path, program: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any]:
    'Run one program, crossing a real candidate-process boundary at restart.'

    segments: list[tuple[int, int]] = []
    start = 0
    for index, event in enumerate(program):
        if str(event.get("type")) == "restart" and index > start:
            segments.append((start, index))
            start = index
    segments.append((start, len(program)))

    snapshot: Mapping[str, Any] | None = None
    now = 0.0
    tags: Mapping[str, Any] = {}
    records: list[Mapping[str, Any]] = []
    published: list[Mapping[str, Any]] = []
    stdout: list[str] = []
    for first, last in segments:
        payload: dict[str, Any] = {
            "events": [dict(event) for event in program[first:last]],
            "index_offset": first,
            "start_time": now,
            "tags": dict(tags),
        }
        if snapshot is not None:
            payload["snapshot"] = dict(snapshot)
        result = PROJECT.invoke(Path(artifact_dir), payload)
        if not result.get("ok"):
            return result
        raw_snapshot = result.get("snapshot")
        if not isinstance(raw_snapshot, Mapping):
            return {
                "ok": False,
                "error": "candidate session returned no BrokerState snapshot",
            }
        raw_tags = result.get("tags")
        if not isinstance(raw_tags, Mapping):
            return {
                "ok": False,
                "error": "candidate session returned no delivery-tag map",
            }
        snapshot = dict(raw_snapshot)
        tags = dict(raw_tags)
        now = float(result.get("now", now))
        records.extend(
            dict(record)
            for record in result.get("records", ())
            if isinstance(record, Mapping)
        )
        published.extend(
            dict(item)
            for item in result.get("published", ())
            if isinstance(item, Mapping)
        )
        if result.get("candidate_stdout"):
            stdout.append(str(result["candidate_stdout"]))
    return {
        "ok": True,
        "records": records,
        "published": published,
        "candidate_stdout": "".join(stdout)[-2000:],
        "snapshot": dict(snapshot or {}),
        "now": now,
        "tags": dict(tags),
    }


def _state(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("state")
    return dict(value) if isinstance(value, Mapping) else {}


def _queues(state: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(queue): [dict(message) for message in messages]
        for queue, messages in dict(state.get("queues", {})).items()
    }


def _residents(state: Mapping[str, Any]) -> list[tuple[str, str, Mapping[str, Any]]]:
    'Every message copy the broker still holds, as (id, queue, message).'

    rows: list[tuple[str, str, Mapping[str, Any]]] = []
    for queue, messages in _queues(state).items():
        for message in messages:
            rows.append((str(message.get("id")), queue, message))
    for entry in dict(state.get("unacked", {})).values():
        message = dict(entry.get("message", {}))
        rows.append((str(message.get("id")), str(entry.get("queue")), message))
    return rows


def _by_label(records: Sequence[Mapping[str, Any]], label: str) -> Mapping[str, Any] | None:
    return next((record for record in records if str(record.get("label")) == label), None)


def _delivered_id(record: Mapping[str, Any] | None) -> str | None:
    'The id this `get` handed out, or None when it handed out nothing.'

    if record is None or not isinstance(record.get("delivery"), Mapping):
        return None
    message = dict(dict(record["delivery"]).get("message", {}))
    identifier = message.get("id")
    return None if identifier is None else str(identifier)


def _phase(records: Sequence[Mapping[str, Any]], phase: str) -> list[Mapping[str, Any]]:
    return [record for record in records if str(record.get("phase")) == phase]


def _listed(identifiers: Sequence[str]) -> str:
    'A list of copies as the dashboard reads it out, never an empty phrase.'

    rows = [str(item) for item in identifiers]
    if not rows:
        return "nothing"
    if len(rows) == 1:
        return rows[0]
    return f"{', '.join(rows[:-1])} and {rows[-1]}"


def _dead_letter_queues(specs: Mapping[str, Mapping[str, Any]]) -> set[str]:
    return {
        str(spec["dead_letter_queue"])
        for spec in specs.values()
        if spec.get("dead_letter_queue")
    }


def _settlements(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in state.get("settled", ()) if isinstance(item, Mapping)]


def _history_rows(headers: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = headers.get("x-death")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _history_gap(
    headers: Mapping[str, Any],
    *,
    required_queue: str | None = None,
    required_reason: str | None = None,
) -> str | None:
    "The first operator-visible problem in one copy's movement history."

    history = _history_rows(headers)
    if not history:
        return _PROVENANCE_GAP["history"]
    for entry in history:
        try:
            count = int(entry.get("count", 0))
            float(entry.get("time"))
        except (TypeError, ValueError):
            return _PROVENANCE_GAP["history"]
        if not entry.get("queue") or not entry.get("reason") or count < 1:
            return _PROVENANCE_GAP["history"]
    if required_queue is not None and required_reason is not None and not any(
        str(entry.get("queue")) == required_queue
        and str(entry.get("reason")) == required_reason
        for entry in history
    ):
        return _PROVENANCE_GAP["event"]
    if (
        headers.get("x-first-death-queue") != history[0].get("queue")
        or headers.get("x-first-death-reason") != history[0].get("reason")
    ):
        return _PROVENANCE_GAP["summary"]
    return None


def _history_count(headers: Mapping[str, Any], queue: str, reason: str) -> int:
    total = 0
    for entry in _history_rows(headers):
        if str(entry.get("queue")) != queue or str(entry.get("reason")) != reason:
            continue
        try:
            total += int(entry.get("count", 0))
        except (TypeError, ValueError):
            return -1
    return total


def _disposition_failures(
    records: Sequence[Mapping[str, Any]],
    published: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        if not record.get("ok") or record.get("state_error"):
            failures.append(
                {
                    "kind": "broker_operation_failed",
                    "phase": record.get("phase"),
                    "label": record.get("label"),
                    "operation": record.get("type"),
                    "error": record.get("error") or record.get("state_error"),
                    "detail": "the step raised instead of completing",
                }
            )
    if failures:
        return failures

    dead_letter_queues = _dead_letter_queues(specs)
    for phase in PHASES:
        phase_records = _phase(records, phase)
        if not phase_records:
            continue
        final = _state(phase_records[-1])
        indexes = {int(record.get("index", -1)) for record in phase_records}


        bodies = {
            str(item["message_id"]): item.get("body")
            for item in published
            if str(item.get("phase")) == phase
        }
        payload_failures: set[tuple[str, str]] = set()
        provenance_failures: set[tuple[str, str, str]] = set()
        multiplicity_failures: set[tuple[str, str, str]] = set()
        rejection_counts: dict[tuple[str, str], int] = defaultdict(int)
        previous_settled: list[dict[str, Any]] = []

        for record in phase_records:
            state = _state(record)
            current_settled = _settlements(state)
            label = str(record.get("label", ""))
            operation = str(record.get("type", ""))


            current_settled_copies: dict[tuple[str, str], int] = defaultdict(int)
            current_resident_copies: dict[tuple[str, str], int] = defaultdict(int)
            for entry in current_settled:
                current_settled_copies[
                    (str(entry.get("message_id")), str(entry.get("queue")))
                ] += 1
            for identifier, queue, _ in _residents(state):
                current_resident_copies[(identifier, queue)] += 1
            for identifier, queue in sorted(
                set(current_settled_copies) | set(current_resident_copies)
            ):
                settled = current_settled_copies[(identifier, queue)]
                resident = current_resident_copies[(identifier, queue)]
                entry = {
                    "phase": phase,
                    "label": label,
                    "message_id": identifier,
                    "queue": queue,
                }
                if settled and resident:
                    kind = "message_settled_and_resident"
                    detail = "the ledger says it is finished and it is still in the queue"
                    measured: dict[str, Any] = {}
                elif settled > 1:
                    kind = "message_settled_more_than_once"
                    detail = "the ledger holds more than one line for this copy"
                    measured = {"entries": settled}
                elif resident > 1:
                    kind = "message_resident_twice"
                    detail = "the same copy is counted twice in one queue"
                    measured = {"places": resident}
                else:
                    continue
                key = (kind, identifier, queue)
                if key not in multiplicity_failures:
                    multiplicity_failures.add(key)
                    failures.append(
                        {**entry, "kind": kind, **measured, "detail": detail}
                    )

            if (
                len(current_settled) < len(previous_settled)
                or current_settled[: len(previous_settled)] != previous_settled
            ):
                failures.append(
                    {
                        "kind": "settlement_record_wrong",
                        "phase": phase,
                        "label": label,
                        "message_id": "ledger",
                        "queue": "console",
                        "recorded_disposition": "rewritten",
                        "recorded_reason": None,
                        "detail": "an earlier console line changed during a later operation",
                    }
                )
                new_settlements: list[dict[str, Any]] = []
            else:
                new_settlements = current_settled[len(previous_settled) :]

            worked_on = (
                _settled_copy(phase_records, record)
                if operation in ("ack", "reject")
                else None
            )
            for entry in new_settlements:
                identifier = str(entry.get("message_id"))
                queue = str(entry.get("queue"))
                disposition = str(entry.get("disposition"))
                raw_reason = entry.get("reason")
                reason = None if raw_reason is None else str(raw_reason)
                target = dict(specs.get(queue, {})).get("dead_letter_queue")
                expected_disposition = (
                    "dead_lettered"
                    if target is not None and str(target) in specs
                    else "dropped"
                )

                if reason is None:
                    causal = (
                        operation == "ack"
                        and worked_on == (identifier, queue)
                        and disposition == "acknowledged"
                    )
                elif reason == "rejected":
                    causal = (
                        operation == "reject"
                        and worked_on == (identifier, queue)
                        and disposition == expected_disposition
                    )
                elif reason == "expired":
                    causal = (
                        operation in ("get", "drain_expired")
                        and str(record.get("queue")) == queue
                        and disposition == expected_disposition
                    )
                elif reason == "maxlen":
                    causal = (
                        operation in ("publish", "get", "reject", "drain_expired")
                        and dict(specs.get(queue, {})).get("max_length") is not None
                        and disposition == expected_disposition
                    )
                else:
                    causal = False
                if identifier not in bodies:
                    causal = False
                if not causal:
                    failures.append(
                        {
                            "kind": "settlement_record_wrong",
                            "phase": phase,
                            "label": label,
                            "message_id": identifier,
                            "queue": queue,
                            "recorded_disposition": disposition,
                            "recorded_reason": reason,
                            "detail": (
                                "the console line does not describe the copy and operation "
                                "that made it leave"
                            ),
                        }
                    )

            if operation == "reject" and worked_on is not None:
                rejection_counts[worked_on] += 1


            representations: list[
                tuple[str, str, Mapping[str, Any], str | None, bool]
            ] = []
            representations.extend(
                (identifier, queue, message, None, queue in dead_letter_queues)
                for identifier, queue, message in _residents(state)
            )
            representations.extend(
                (
                    str(entry.get("message_id")),
                    str(entry.get("queue")),
                    entry,
                    None if entry.get("reason") is None else str(entry.get("reason")),
                    (
                        entry.get("reason") is not None
                        or str(entry.get("queue")) in dead_letter_queues
                    ),
                )
                for entry in current_settled
            )
            delivery = record.get("delivery")
            if isinstance(delivery, Mapping):
                message = dict(delivery.get("message", {}))
                queue = str(record.get("queue", message.get("queue", "")))
                representations.append(
                    (
                        str(message.get("id")),
                        queue,
                        message,
                        None,
                        queue in dead_letter_queues,
                    )
                )

            for identifier, queue, message, required_reason, needs_history in representations:
                if identifier in bodies and message.get("body") != bodies[identifier]:
                    key = (identifier, queue)
                    if key not in payload_failures:
                        payload_failures.add(key)
                        failures.append(
                            {
                                "kind": "dead_letter_payload_altered",
                                "phase": phase,
                                "label": label,
                                "message_id": identifier,
                                "queue": queue,
                                "arrived_with": message.get("body"),
                                "detail": (
                                    "the copy no longer carries the content it was "
                                    "published with"
                                ),
                            }
                        )
                headers = dict(message.get("headers", {}))
                gap = (
                    _history_gap(
                        headers,
                        required_queue=queue if required_reason is not None else None,
                        required_reason=required_reason,
                    )
                    if needs_history
                    else (
                        _history_gap(headers)
                        if _history_rows(headers)
                        else None
                    )
                )
                if gap is not None:
                    key = (identifier, queue, gap)
                    if key not in provenance_failures:
                        provenance_failures.add(key)
                        failures.append(
                            {
                                "kind": "dead_letter_provenance_missing",
                                "phase": phase,
                                "label": label,
                                "message_id": identifier,
                                "queue": queue,
                                "missing": gap,
                                "detail": _PROVENANCE_DETAIL,
                            }
                        )

            if operation == "reject" and worked_on is not None:
                identifier, queue = worked_on
                expected_count = rejection_counts[worked_on]
                matching_counts = [
                    _history_count(dict(message.get("headers", {})), queue, "rejected")
                    for represented_id, _, message, _, _ in representations
                    if represented_id == identifier
                ]
                if expected_count not in matching_counts:
                    gap = _PROVENANCE_GAP["count"]
                    key = (identifier, queue, gap)
                    if key not in provenance_failures:
                        provenance_failures.add(key)
                        failures.append(
                            {
                                "kind": "dead_letter_provenance_missing",
                                "phase": phase,
                                "label": label,
                                "message_id": identifier,
                                "queue": queue,
                                "missing": gap,
                                "recorded_rejections": max(matching_counts, default=0),
                                "observed_rejections": expected_count,
                                "detail": _PROVENANCE_DETAIL,
                            }
                        )
            previous_settled = current_settled

        settled_copies: dict[tuple[str, str], int] = defaultdict(int)
        resident_copies: dict[tuple[str, str], int] = defaultdict(int)
        for entry in _settlements(final):
            settled_copies[(str(entry.get("message_id")), str(entry.get("queue")))] += 1
        for identifier, queue, message in _residents(final):
            resident_copies[(identifier, queue)] += 1
        for entry in _settlements(final):
            if str(entry.get("disposition")) != "dead_lettered":
                continue
            identifier = str(entry.get("message_id"))
            source = str(entry.get("queue"))
            target = dict(specs.get(source, {})).get("dead_letter_queue")
            arrived = target is not None and (
                resident_copies.get((identifier, str(target)), 0) > 0
                or settled_copies.get((identifier, str(target)), 0) > 0
            )
            if not arrived:
                failures.append(
                    {
                        "kind": "dead_lettered_copy_never_arrived",
                        "phase": phase,
                        "message_id": identifier,
                        "queue": source,
                        "dead_letter_queue": target,
                        "detail": (
                            "the ledger says it moved to the dead-letter queue and "
                            "no copy of it ever arrived there"
                        ),
                    }
                )
        copies = set(settled_copies) | set(resident_copies)
        copies.update(
            (str(item["message_id"]), str(item["queue"]))
            for item in published
            if int(item.get("index", -1)) in indexes
        )
        for identifier, queue in sorted(copies):
            settled = settled_copies[(identifier, queue)]
            resident = resident_copies[(identifier, queue)]
            entry = {"phase": phase, "message_id": identifier, "queue": queue}
            if settled + resident == 0:
                failures.append(
                    {
                        **entry,
                        "kind": "message_unaccounted",
                        "detail": "the copy is in no queue and has no ledger entry",
                    }
                )
    return failures


def _redelivery_failures(
    records: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    dead_letter_queues = _dead_letter_queues(specs)
    handouts: dict[tuple[str, str], int] = defaultdict(int)
    for record in records:
        if str(record.get("type")) != "get":
            continue
        delivery = record.get("delivery")
        if not isinstance(delivery, Mapping):
            continue
        message = dict(delivery.get("message", {}))
        queue = str(record.get("queue", message.get("queue")))
        key = (str(message.get("id")), queue)
        earlier = handouts[key]
        reported = delivery.get("redelivery_count")
        reported = 0 if reported is None else int(reported)
        if reported != earlier:
            common = {
                "phase": record.get("phase"),
                "label": record.get("label"),
                "message_id": key[0],
                "queue": queue,
                "reported": reported,
                "earlier_handouts_from_this_queue": earlier,
            }
            if earlier == 0 and reported > 0 and queue in dead_letter_queues:
                failures.append({**common, "kind": "redelivery_count_not_reset"})
            elif reported == earlier + 1:
                failures.append({**common, "kind": "redelivery_count_off_by_one"})
            else:
                failures.append(
                    {
                        **common,
                        "kind": "redelivery_count_wrong",
                        "detail": "the number does not match the handouts that came before it",
                    }
                )
        handouts[key] += 1
        allowance = int(dict(specs.get(queue, {})).get("max_deliveries", 3))
        if handouts[key] > allowance:
            failures.append(
                {
                    "kind": "redelivery_bound_exceeded",
                    "phase": record.get("phase"),
                    "label": record.get("label"),
                    "message_id": key[0],
                    "queue": queue,
                    "handouts": handouts[key],
                    "allowance": allowance,
                    "detail": "one copy was handed out more times than the queue allows",
                }
            )
    poison = _phase(records, "poison")
    if poison:
        final = _state(poison[-1])
        first = _delivered_id(_by_label(poison, "take-1"))
        for label in ("take-2", "take-3"):
            handed_out = _delivered_id(_by_label(poison, label))
            if first is not None and handed_out is not None and handed_out != first:
                failures.append(
                    {
                        "kind": "requeue_order_wrong",
                        "phase": "poison",
                        "label": label,
                        "queue": "work",
                        "message_id": first,
                        "handed_out": handed_out,
                        "detail": (
                            "the next worker was not handed the copy the previous "
                            "worker returned for another attempt"
                        ),
                    }
                )
                break


        waiting = [str(message.get("id")) for message in _queues(final).get("work", [])]
        if waiting:
            failures.append(
                {
                    "kind": "poison_message_retained",
                    "phase": "poison",
                    "queue": "work",


                    "message_id": waiting[0],
                    "message_ids": sorted(set(waiting))[:4],
                    "detail": "the failing copy is still first in line where the workers take from",
                }
            )
        discarded = _delivered_id(_by_label(poison, "take-5"))
        after = _delivered_id(_by_label(poison, "take-6"))
        if discarded is not None and after is not None and after == discarded:
            failures.append(
                {
                    "kind": "discarded_message_redelivered",
                    "phase": "poison",
                    "label": "take-6",
                    "queue": "work",
                    "message_id": after,
                    "detail": (
                        "the handout after the discard came back holding the copy "
                        "the worker had just thrown away"
                    ),
                }
            )
    return failures


def _publisher_lifetime_failures(
    records: Sequence[Mapping[str, Any]],
    program: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'Each publish that named its own lifetime, against the copy it stored.'

    asked: dict[str, tuple[float, list[str]]] = {}
    for event in program:
        if str(event.get("type")) != "publish" or event.get("ttl") is None:
            continue
        asked[str(event.get("label"))] = (
            float(event["ttl"]),
            [str(queue) for queue in event.get("queues", ())],
        )
    failures: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("type")) != "publish":
            continue
        entry = asked.get(str(record.get("label")))
        if entry is None:
            continue
        lifetime, queues = entry
        now = float(record.get("now", 0.0))
        waiting = _queues(_state(record))
        identifiers = [str(item) for item in record.get("message_ids", ())]
        for queue, identifier in zip(queues, identifiers):
            queue_ttl = dict(specs.get(queue, {})).get("message_ttl")
            if queue_ttl is None or float(queue_ttl) >= lifetime:
                continue


            copy = next(
                (
                    message
                    for message in waiting.get(queue, [])
                    if str(message.get("id")) == identifier
                ),
                None,
            )
            if copy is None:
                continue
            deadline = copy.get("expires_at")
            if deadline is not None and abs(float(deadline) - (now + lifetime)) <= 1e-6:
                continue
            failures.append(
                {
                    "kind": "publisher_lifetime_shortened",
                    "phase": record.get("phase"),
                    "label": record.get("label"),
                    "queue": queue,
                    "message_id": identifier,
                    "expires_at": deadline,
                    "published_with_ttl": lifetime,
                    "queue_message_ttl": float(queue_ttl),
                    "detail": (
                        "the copy is carrying the queue's own lifetime instead of "
                        "the longer one it was published with"
                    ),
                }
            )
    return failures


def _expiry_failures(
    records: Sequence[Mapping[str, Any]],
    program: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    from .workload import ALERT_TTL_SECONDS, SLOW_ALERT_TTL_SECONDS

    failures: list[dict[str, Any]] = list(
        _publisher_lifetime_failures(records, program, specs)
    )
    for record in records:
        if str(record.get("type")) != "get":
            continue
        now = float(record.get("now", 0.0))
        delivery = record.get("delivery")
        if isinstance(delivery, Mapping):
            message = dict(delivery.get("message", {}))
            expires_at = message.get("expires_at")
            if expires_at is not None and float(expires_at) <= now:
                failures.append(
                    {
                        "kind": "expired_message_delivered",
                        "phase": record.get("phase"),
                        "label": record.get("label"),
                        "message_id": message.get("id"),
                        "queue": record.get("queue"),
                        "expires_at": expires_at,
                        "handed_out_at": now,
                        "detail": "a worker was handed a copy whose deadline had already passed",
                    }
                )
        served = str(record.get("queue", ""))
        stale = [
            str(message.get("id"))
            for message in _queues(_state(record)).get(served, [])
            if message.get("expires_at") is not None
            and float(message["expires_at"]) <= now
        ]
        if stale:
            failures.append(
                {
                    "kind": "expired_copy_left_waiting_after_handout",
                    "phase": record.get("phase"),
                    "label": record.get("label"),
                    "queue": served,
                    "message_ids": sorted(set(stale))[:4],
                    "clock": now,
                    "detail": (
                        "the handout stepped over a copy past its deadline and left "
                        "it waiting in the queue"
                    ),
                }
            )
    failures.extend(_sweep_and_leftover_failures(records))
    ttl_records = _phase(records, "ttl")
    if not ttl_records:
        return failures
    fanout = _by_label(ttl_records, "pub-fanout")
    if fanout is not None:
        queues = _queues(_state(fanout))
        deadlines = {
            queue: [message.get("expires_at") for message in messages]
            for queue, messages in queues.items()
            if messages
        }
        for queue, expected in (
            ("alerts", ALERT_TTL_SECONDS),
            ("alerts.slow", SLOW_ALERT_TTL_SECONDS),
        ):
            waiting = queues.get(queue, [])
            deadline = waiting[-1].get("expires_at") if waiting else None
            if deadline is None or abs(float(deadline) - float(expected)) > 1e-6:
                failures.append(
                    {
                        "kind": "queue_ttl_not_applied",
                        "phase": "ttl",
                        "label": "pub-fanout",
                        "queue": queue,
                        "message_id": waiting[-1].get("id") if waiting else None,
                        "expires_at": deadline,
                        "published_at": waiting[-1].get("published_at") if waiting else None,
                        "queue_message_ttl": expected,
                        "deadlines": deadlines,
                    }
                )
    short = _by_label(ttl_records, "pub-short")
    if short is not None:
        waiting = _queues(_state(short)).get("alerts", [])
        deadline = waiting[-1].get("expires_at") if waiting else None
        if deadline is None or abs(float(deadline) - 5.0) > 1e-6:
            failures.append(
                {
                    "kind": "message_ttl_not_applied",
                    "phase": "ttl",
                    "label": "pub-short",
                    "queue": "alerts",
                    "message_id": waiting[-1].get("id") if waiting else None,
                    "expires_at": deadline,
                    "published_with_ttl": 5.0,
                }
            )
    return failures


def _sweep_and_leftover_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "Every sweep's count, and what is still waiting when each drill stops."

    failures: list[dict[str, Any]] = []
    for position, record in enumerate(records):
        if str(record.get("type")) != "drain_expired":
            continue
        queue = str(record.get("queue", ""))
        now = float(record.get("now", 0.0))

        before = _queues(_state(records[position - 1])) if position else {}
        expected = sum(
            1
            for message in before.get(queue, [])
            if message.get("expires_at") is not None
            and float(message["expires_at"]) <= now
        )
        reported = record.get("expired")
        if reported is None or int(reported) != expected:
            failures.append(
                {
                    "kind": "drain_expired_count_wrong",
                    "phase": record.get("phase"),
                    "label": record.get("label"),
                    "queue": queue,
                    "reported": reported,
                    "past_their_deadline": expected,
                    "clock": now,
                    "detail": "the sweep reported a different number than it removed",
                }
            )
    for phase in PHASES:
        phase_records = _phase(records, phase)
        if not phase_records:
            continue
        final = phase_records[-1]
        now = float(final.get("now", 0.0))
        for queue, messages in sorted(_queues(_state(final)).items()):
            for message in messages:
                expires_at = message.get("expires_at")
                if expires_at is not None and float(expires_at) <= now:
                    failures.append(
                        {
                            "kind": "expired_message_retained",
                            "phase": phase,
                            "queue": queue,
                            "message_id": message.get("id"),
                            "expires_at": expires_at,
                            "clock": now,
                        }
                    )
    return failures


def _victim_age_failures(
    records: Sequence[Mapping[str, Any]],
    capped: Mapping[str, int],
    published: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    "Nothing older than a capped queue's victim may remain waiting."

    failures: list[dict[str, Any]] = []
    clocks = {
        int(record.get("index", -1)): float(record.get("now", 0.0))
        for record in records
    }
    entered: dict[tuple[str, str, str], float] = {
        (
            str(item.get("phase")),
            str(item.get("message_id")),
            str(item.get("queue")),
        ): clocks.get(int(item.get("index", -1)), 0.0)
        for item in published
    }
    previous_by_phase: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        phase = str(record.get("phase", ""))
        after = _state(record)
        earlier = previous_by_phase.get(phase, [])
        current = _settlements(after)
        if len(current) < len(earlier) or current[: len(earlier)] != earlier:
            previous_by_phase[phase] = current
            continue
        now = float(record.get("now", 0.0))
        waiting = _queues(after)
        for entry in (dict(item) for item in current[len(earlier) :]):
            queue = str(entry.get("queue"))
            identifier = str(entry.get("message_id"))
            if str(entry.get("reason")) == "maxlen" and queue in capped:
                since = entered.get((phase, identifier, queue))
                older = [] if since is None else [
                    (message, entered[(phase, str(message.get("id")), queue)])
                    for message in waiting.get(queue, [])
                    if (phase, str(message.get("id")), queue) in entered
                    and entered[(phase, str(message.get("id")), queue)] < since
                ]
                if older:
                    kept, kept_since = min(older, key=lambda item: item[1])
                    failures.append(
                        {
                            "kind": "overflow_kept_an_older_copy",
                            "phase": phase,
                            "label": record.get("label"),
                            "queue": queue,
                            "message_id": identifier,
                            "waiting_since": since,
                            "kept": str(kept.get("id")),
                            "kept_since": kept_since,
                            "detail": (
                                "the queue shed a copy and kept one that had been "
                                "waiting in it for longer"
                            ),
                        }
                    )

            if str(entry.get("disposition")) == "dead_lettered":
                target = dict(specs.get(queue, {})).get("dead_letter_queue")
                if target is not None and str(target) in specs:
                    entered[(phase, identifier, str(target))] = now
        previous_by_phase[phase] = current
    return failures


def _overflow_failures(
    records: Sequence[Mapping[str, Any]],
    published: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    capped = {
        name: int(spec["max_length"])
        for name, spec in specs.items()
        if spec.get("max_length") is not None
    }


    previous_unacked: dict[str, tuple[str, str]] = {}
    for record in records:
        state = _state(record)
        queues = _queues(state)
        for queue, cap in capped.items():
            waiting = queues.get(queue, [])
            if len(waiting) > cap:
                failures.append(
                    {
                        "kind": "queue_length_bound_exceeded",
                        "phase": record.get("phase"),
                        "label": record.get("label"),
                        "queue": queue,
                        "waiting": len(waiting),
                        "max_length": cap,
                    }
                )
        current = {
            str(tag): (
                str(dict(entry.get("message", {})).get("id")),
                str(entry.get("queue")),
            )
            for tag, entry in dict(state.get("unacked", {})).items()
        }
        if str(record.get("type")) not in ("ack", "reject", "restart", "reset"):
            vanished = sorted(set(previous_unacked).difference(current))
            if vanished:
                message_id, queue = previous_unacked[vanished[0]]
                failures.append(
                    {
                        "kind": "unacked_message_evicted",
                        "phase": record.get("phase"),
                        "label": record.get("label"),
                        "message_id": message_id,
                        "queue": queue,
                        "delivery_tags": vanished[:4],
                        "detail": "a copy a worker was already holding disappeared from the broker",
                    }
                )
        previous_unacked = current
    failures.extend(_victim_age_failures(records, capped, published, specs))

    overflow = _phase(records, "overflow")
    if not overflow:
        return failures
    final = _state(overflow[-1])
    queues = _queues(final)
    ids_by_label = {
        str(item["label"]): str(item["message_id"])
        for item in published
        if str(item["queue"]) == "feed" and str(item.get("phase")) == "overflow"
    }
    surviving = [str(message.get("id")) for message in queues.get("feed", [])]
    position_split = _by_label(overflow, "reject-feed-1") is not None
    survivor_indices = (2, 4, 5) if position_split else (5, 6, 7)
    expected = [
        ids_by_label[f"pub-p{index}"]
        for index in survivor_indices
        if f"pub-p{index}" in ids_by_label
    ]
    if surviving != expected:
        failures.append(
            {
                "kind": "overflow_evicted_wrong_message",
                "phase": "overflow",
                "queue": "feed",
                "still_waiting": surviving,
                "oldest_first_would_leave": expected,


                "still_waiting_ids": _listed(surviving),
                "should_still_be_waiting": _listed(expected),
            }
        )
    shed = {
        str(item["message_id"])
        for item in (dict(row) for row in final.get("settled", ()))
        if str(item.get("reason")) == "maxlen"
    }
    shed_indices = (1,) if position_split else (1, 2, 4)
    should_shed = {
        ids_by_label[f"pub-p{index}"]
        for index in shed_indices
        if f"pub-p{index}" in ids_by_label
    }
    if not should_shed.issubset(shed):
        unrecorded = sorted(should_shed.difference(shed))
        failures.append(
            {
                "kind": "overflow_victim_not_dead_lettered",
                "phase": "overflow",
                "queue": "feed.dead",
                "message_id": unrecorded[0],
                "not_recorded_as_shed": unrecorded,
                "recorded_as_shed": sorted(shed),
            }
        )
    side = queues.get("side", [])
    if len(side) != 1:
        failures.append(
            {
                "kind": "unrelated_queue_disturbed",
                "phase": "overflow",
                "queue": "side",
                "waiting": len(side),
                "published_there": 1,
            }
        )
    return failures


def _settled_copy(
    phase_records: Sequence[Mapping[str, Any]], record: Mapping[str, Any]
) -> tuple[str, str] | None:
    'The (copy, queue) an ack or reject worked on, read from the handout it names.'

    source = _by_label(phase_records, str(record.get("tag_of") or ""))
    identifier = _delivered_id(source)
    if source is None or identifier is None:
        return None
    return identifier, str(source.get("queue", ""))


def _live(messages: Sequence[Mapping[str, Any]], now: float) -> bool:
    'Whether any copy waiting here is one a worker could still be handed.'

    return any(
        message.get("expires_at") is None or float(message["expires_at"]) > now
        for message in messages
    )


def _one_restart(
    phase: str,
    phase_records: Sequence[Mapping[str, Any]],
    position: int,
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'What one deploy in one phase cost, measured across the restart record.'

    failures: list[dict[str, Any]] = []
    if position == 0 or position == len(phase_records) - 1:
        return [
            {
                "kind": "post_restart_delivery_failed",
                "phase": phase,
                "label": phase_records[position].get("label"),
                "detail": "there is nothing recorded around the restart",
            }
        ]


    before_state = _state(phase_records[position - 1])
    after_state = _state(phase_records[position])
    before_ledger = _settlements(before_state)
    after_ledger = _settlements(after_state)
    if after_ledger != before_ledger:
        failures.append(
            {
                "kind": "restart_lost_settlement_record",
                "phase": phase,
                "label": phase_records[position].get("label"),
                "settled_before": len(before_ledger),
                "settled_after": len(after_ledger),
                "detail": "the settlement ledger changed while the broker restarted",
            }
        )
    before_copies = {(identifier, queue) for identifier, queue, _ in _residents(before_state)}
    after_copies = {(identifier, queue) for identifier, queue, _ in _residents(after_state)}
    missing = sorted(before_copies.difference(after_copies))
    dead_letter = {queue for queue in _queues(before_state) if queue.endswith(".dead")}
    lost_dead = sorted(pair for pair in missing if pair[1] in dead_letter)
    lost_live = sorted(pair for pair in missing if pair[1] not in dead_letter)
    if lost_live:
        failures.append(
            {
                "kind": "restart_lost_resident_message",
                "phase": phase,
                "label": phase_records[position].get("label"),
                "message_id": lost_live[0][0],
                "queue": lost_live[0][1],
                "gone_after_the_restart": lost_live[:4],
            }
        )
    if lost_dead:
        failures.append(
            {
                "kind": "restart_lost_dead_letters",
                "phase": phase,
                "label": phase_records[position].get("label"),
                "message_id": lost_dead[0][0],
                "queue": lost_dead[0][1],
                "gone_after_the_restart": lost_dead[:4],
            }
        )
    acknowledged = {
        str(item.get("message_id"))
        for item in (dict(row) for row in before_state.get("settled", ()))
        if str(item.get("disposition")) == "acknowledged"
    }
    back = sorted(
        {
            (identifier, queue)
            for identifier, queue, _ in _residents(after_state)
            if identifier in acknowledged
        }
    )
    if back:
        failures.append(
            {
                "kind": "acknowledged_message_resurrected",
                "phase": phase,
                "label": phase_records[position].get("label"),
                "message_id": back[0][0],
                "queue": back[0][1],
                "back_in_a_queue": back[:4],
            }
        )


    for index in range(position + 1, len(phase_records)):
        record = phase_records[index]
        if str(record.get("type")) != "get" or not record.get("ok"):
            continue
        if isinstance(record.get("delivery"), Mapping):
            continue
        queue = str(record.get("queue", ""))
        waiting = _queues(_state(phase_records[index - 1])).get(queue, [])
        if _live(waiting, float(record.get("now", 0.0))):
            failures.append(
                {
                    "kind": "post_restart_delivery_failed",
                    "phase": phase,
                    "label": record.get("label"),
                    "queue": queue,
                    "waiting_before_it": [str(message.get("id")) for message in waiting][:4],
                    "detail": "the queue handed out nothing after the restart",
                }
            )


    rejections: dict[tuple[str, str], int] = defaultdict(int)
    for index, record in enumerate(phase_records):
        if str(record.get("type")) != "reject" or not record.get("requeue"):
            continue
        copy = _settled_copy(phase_records, record)
        if copy is None:
            continue
        earlier = rejections[copy]
        rejections[copy] += 1
        allowance = int(dict(specs.get(copy[1], {})).get("max_deliveries", 3))
        if index < position or earlier == 0 or rejections[copy] < allowance:
            continue
        resident = [
            queue
            for identifier, queue, _ in _residents(_state(record))
            if identifier == copy[0] and queue == copy[1]
        ]
        if resident:
            failures.append(
                {
                    "kind": "restart_lost_redelivery_state",
                    "phase": phase,
                    "label": record.get("label"),
                    "message_id": copy[0],
                    "queue": copy[1],
                    "rejections_before_the_deploy": earlier,
                    "detail": "it went back into the queue on the rejection after the restart",
                }
            )
    return failures


def _restart_failures(
    records: Sequence[Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'Every deploy in the drill, judged where it happened.'

    failures: list[dict[str, Any]] = []
    for phase in PHASES:
        phase_records = _phase(records, phase)
        for position, record in enumerate(phase_records):
            if str(record.get("type")) == "restart":
                failures.extend(_one_restart(phase, phase_records, position, specs))
    return failures


def _records_with_phase(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    phases = {int(index): str(event.get("phase", "")) for index, event in enumerate(program)}
    return [
        {**dict(record), "phase": phases.get(int(record.get("index", -1)), "")}
        for record in candidate.get("records", ())
        if isinstance(record, Mapping)
    ]


def _analyse(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    records = _records_with_phase(candidate, program)
    phases = {int(index): str(event.get("phase", "")) for index, event in enumerate(program)}
    published = [
        {**dict(item), "phase": phases.get(int(item.get("index", -1)), "")}
        for item in candidate.get("published", ())
        if isinstance(item, Mapping)
    ]
    specs = queue_specs(program)
    execution_failures = [
        {
            "kind": "candidate_process_failure",
            "phase": record.get("phase"),
            "label": record.get("label"),
            "error": _console_error(
                {
                    "error": record.get("error")
                    or record.get("state_error")
                    or "one operation did not complete"
                }
            ),
        }
        for record in records
        if not record.get("ok") or record.get("state_error")
    ]
    redelivery = _redelivery_failures(records, specs)
    expiry = _expiry_failures(records, program, specs)
    overflow = _overflow_failures(records, published, specs)
    restart = _restart_failures(records, specs)
    record_indexes = {
        (str(record.get("phase", "")), str(record.get("label", ""))): int(
            record.get("index", -1)
        )
        for record in records
    }
    failed_at = [
        int(record.get("index", -1))
        for record in records
        if not record.get("ok") or record.get("state_error")
    ]
    first_incomplete = min(failed_at) if failed_at else None

    def measured_or_incomplete(
        measured: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:


        if first_incomplete is None:
            return measured
        reliable = [
            failure
            for failure in measured
            if record_indexes.get(
                (str(failure.get("phase", "")), str(failure.get("label", ""))),
                first_incomplete,
            )
            < first_incomplete
        ]
        return reliable if reliable else list(execution_failures)

    return {
        "disposition_failures": _disposition_failures(records, published, specs),
        "redelivery_failures": measured_or_incomplete(redelivery),
        "expiry_failures": measured_or_incomplete(expiry),
        "overflow_failures": measured_or_incomplete(overflow),
        "restart_failures": measured_or_incomplete(restart),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)


_TIMEOUT_PHRASE = "project rehearsal exceeded"


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The single line the operator console shows when a drill did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the drill box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the broker ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    lowered = line.lower()
    if any(word in lowered for word in FORBIDDEN_VOCABULARY):
        line = "the broker ended without saying why"
    return f"the broker stopped before the drill finished: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private drill against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(
            str(PRIVATE_CASE["profile"]),
            int(PRIVATE_CASE["seed"]),
            int(PRIVATE_CASE["scale"]),
        )
        candidate = _invoke_program(artifact_dir, program)
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"drill": "release", "phases": list(PHASES)}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                "scene": raw.get("scene"),
                "queues": raw.get("queue_properties"),
            }
        )
    return {
        "summary": "The broker workspace and the drills the team replays before a change goes out.",
        "measurements": {


            "broker_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "broker").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def _message_row(message: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "message_id": message.get("id"),
        "published_at": message.get("published_at"),
        "expires_at": message.get("expires_at"),
        "headers": message.get("headers"),
    }


def _operation_row(record: Mapping[str, Any], *, full: bool) -> dict[str, Any]:
    state = _state(record)
    queues = _queues(state)
    row: dict[str, Any] = {
        "label": record.get("label"),
        "operation": record.get("type"),
        "clock": record.get("now"),
        "completed": bool(record.get("ok")),
        "error": record.get("error"),
        "waiting": {queue: [str(m.get("id")) for m in messages] for queue, messages in sorted(queues.items())},
        "held_by_workers": [
            {
                "tag": str(tag),
                "queue": entry.get("queue"),
                "message_id": dict(entry.get("message", {})).get("id"),
            }
            for tag, entry in sorted(dict(state.get("unacked", {})).items())
        ],
    }
    if record.get("queue") is not None:
        row["queue"] = record.get("queue")


        row["queue_after_this_operation"] = [
            _message_row(message) for message in queues.get(str(record.get("queue")), [])
        ]
    if record.get("type") == "publish":
        row["published_message_ids"] = record.get("message_ids")
        row["deadlines"] = {
            queue: [
                {
                    "message_id": message.get("id"),
                    "published_at": message.get("published_at"),
                    "expires_at": message.get("expires_at"),
                }
                for message in messages
            ]
            for queue, messages in sorted(queues.items())
            if messages
        }
    if record.get("type") == "get":
        delivery = record.get("delivery")
        if isinstance(delivery, Mapping):
            message = dict(dict(delivery).get("message", {}))
            row["handed_out"] = {
                **_message_row(message),
                "queue": message.get("queue"),
                "redelivery_count": dict(delivery).get("redelivery_count"),
            }
        else:
            row["handed_out"] = None
    if record.get("type") in ("ack", "reject"):


        row["settles"] = record.get("tag_of")
        if record.get("type") == "reject":
            row["requeue"] = record.get("requeue")
    if record.get("type") == "drain_expired":
        row["expired_removed"] = record.get("expired")
    if full:
        row["queue_contents"] = {
            queue: [_message_row(message) for message in messages]
            for queue, messages in sorted(queues.items())
        }
        row["settled"] = [
            {
                "message_id": item.get("message_id"),
                "disposition": item.get("disposition"),
                "reason": item.get("reason"),
                "queue": item.get("queue"),
                "body": item.get("body"),
            }
            for item in (dict(entry) for entry in state.get("settled", ()))
        ]
    return row


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded drill against this workspace and report what happened.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    program = build_program(str(case["profile"]), int(case["seed"]), int(case["scale"]))
    candidate = _invoke_program(Path(artifact_dir), program)
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} drill could not run this broker to the end.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "operator_notes": raw.get("recorded"),
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    records = _records_with_phase(candidate, program)
    last = len(records) - 1
    timeline = [
        _operation_row(record, full=index == last) for index, record in enumerate(records)
    ]
    return {
        "summary": f"The {record_id} drill ran against this broker.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "operation_count": len(timeline),
        },
        "operator_notes": raw.get("recorded"),
        "public": {"operation_timeline": timeline},
    }
