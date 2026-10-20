"""The five binary project rubrics for the notification broker."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "accounted_message_disposition": (
        "candidate_execution_failed",
        "broker_operation_failed",
        "settlement_record_wrong",
        "message_unaccounted",
        "dead_lettered_copy_never_arrived",
        "message_settled_more_than_once",
        "message_settled_and_resident",
        "message_resident_twice",
        "dead_letter_provenance_missing",
        "dead_letter_payload_altered",
    ),
    "bounded_redelivery": (
        "candidate_execution_failed",
        "poison_message_retained",
        "redelivery_bound_exceeded",
        "discarded_message_redelivered",
        "requeue_order_wrong",
        "redelivery_count_off_by_one",
        "redelivery_count_not_reset",
        "redelivery_count_wrong",
    ),
    "publication_time_expiry": (
        "candidate_execution_failed",
        "expired_message_delivered",
        "queue_ttl_not_applied",
        "message_ttl_not_applied",
        "publisher_lifetime_shortened",
        "expired_copy_left_waiting_after_handout",
        "expired_message_retained",
        "drain_expired_count_wrong",
    ),
    "bounded_queue_overflow": (
        "candidate_execution_failed",
        "queue_length_bound_exceeded",
        "unacked_message_evicted",
        "overflow_evicted_wrong_message",
        "overflow_kept_an_older_copy",
        "overflow_victim_not_dead_lettered",
        "unrelated_queue_disturbed",
    ),
    "restart_durable_broker_state": (
        "candidate_execution_failed",
        "post_restart_delivery_failed",
        "restart_lost_settlement_record",
        "restart_lost_resident_message",
        "acknowledged_message_resurrected",
        "restart_lost_dead_letters",
        "restart_lost_redelivery_state",
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple((mode for mode in modes if mode != "candidate_execution_failed"))
    for rubric_id, modes in FAILURE_MODES.items()
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def accounted_message_disposition(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def bounded_redelivery(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def publication_time_expiry(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def bounded_queue_overflow(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def restart_durable_broker_state(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
