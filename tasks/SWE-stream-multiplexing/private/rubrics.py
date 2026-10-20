"The five binary project rubrics for the telemetry uplink."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "frames_the_firmware_accepts": (
        "candidate_execution_failed",
        "frame_the_firmware_cannot_read",
        "frame_over_the_size_cap",
        "payload_before_the_stream_is_open",
        "stream_id_collides_with_the_device",
    ),
    "payload_delivery_is_conserved": (
        "candidate_execution_failed",
        "link_operation_failed",
        "stream_payload_not_delivered",
        "inbound_payload_not_delivered",
        "link_counter_disagrees_with_link",
    ),
    "send_window_bounds_outstanding": (
        "candidate_execution_failed",
        "send_window_overrun",
        "credited_transfer_never_completes",
    ),
    "stalled_stream_does_not_stop_others": (
        "candidate_execution_failed",
        "radio_slot_overrun",
        "ready_stream_never_advanced",
        "ready_stream_incomplete_within_budget",
        "priority_order_not_served",
    ),
    "teardown_is_two_sided_and_drained": (
        "candidate_execution_failed",
        "teardown_operation_failed",
        "close_raised_against_refusing_radio",
        "buffered_inbound_lost_on_close",
        "stream_dropped_before_it_was_drained",
        "local_close_not_signaled",
        "stream_dropped_while_one_end_open",
        "unrelated_stream_closed",
        "stream_left_open_after_teardown",
        "closed_endpoint_accepted_operation",
        "pending_write_never_settled",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple(mode for mode in modes if mode != "candidate_execution_failed")
    for rubric_id, modes in FAILURE_MODES.items()
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def frames_the_firmware_accepts(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def payload_delivery_is_conserved(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def send_window_bounds_outstanding(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def stalled_stream_does_not_stop_others(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def teardown_is_two_sided_and_drained(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
