"""The five binary project checks for the relay client's grant store."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "grant_audience": (
        "candidate_execution_failed",
        "grant_sent_beyond_its_scope",
        "sealed_grant_sent_in_the_clear",
        "grant_sent_outside_its_path",
        "host_only_grant_sent_to_sibling",
        "grant_withheld_from_its_scope",
        "grant_rejected_as_unissued",
    ),
    "grant_lifetime": (
        "candidate_execution_failed",
        "expired_grant_still_presented",
        "revoked_grant_still_presented",
        "unreadable_deadline_dropped_the_grant",
        "grant_rejected_as_unissued",
    ),
    "grant_identity_and_bounds": (
        "candidate_execution_failed",
        "same_grant_presented_twice",
        "refresh_left_two_live_grants",
        "bounds_exceeded",
        "trimmed_grant_returned_after_retirement",
        "trim_dropped_the_established_grant",
        "pressure_survivor_missing_after_retirement",
        "grant_rejected_as_unissued",
    ),
    "fold_invariance": (
        "candidate_execution_failed",
        "folded_reply_lost_a_grant",
        "folded_reply_changed_a_grant",
        "junk_segment_stored_as_a_grant",
        "grant_rejected_as_unissued",
    ),
    "grant_send_order": (
        "candidate_execution_failed",
        "wrong_desk_on_a_scoped_page",
        "wrong_desk_after_re_entering",
        "page_read_with_no_desk_grant",
        "grant_rejected_as_unissued",
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


def grant_audience(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def grant_lifetime(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def grant_identity_and_bounds(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def fold_invariance(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def grant_send_order(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
