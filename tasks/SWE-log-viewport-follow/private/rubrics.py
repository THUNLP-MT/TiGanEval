"The five binary project rubrics for the incident console's rich pane."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "paused_anchor_holds": (
        "candidate_execution_failed",
        "paused_view_jumped_to_the_end",
        "paused_view_slid_under_prune",
        "paused_view_slid_after_reflow",
        "paused_view_slid_after_the_reading_minimum",
        "paused_view_lost_the_row_on_an_unchanged_entry",
    ),
    "liveness_follows_position": (
        "candidate_execution_failed",
        "badge_live_while_scrolled_up",
        "badge_paused_at_the_end",
        "vertical_scrollbar_disagrees_with_pane",
    ),
    "follow_transitions_exactly_once": (
        "candidate_execution_failed",
        "record_posted_without_a_flip",
        "transition_not_posted",
        "record_carried_unsettled_position",
    ),
    "render_matches_reference": (
        "candidate_execution_failed",
        "retained_entries_disagree",
        "deferred_entry_rendered_before_layout",
        "full_width_entry_not_expanded",
        "entry_kept_its_old_width",
        "entry_ignored_the_reading_minimum",
    ),
    "extent_matches_retained": (
        "candidate_execution_failed",
        "content_width_kept_a_pruned_entry",
        "content_width_stops_short_of_the_widest_line",
        "line_count_disagrees_with_the_pane",
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


def paused_anchor_holds(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def liveness_follows_position(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def follow_transitions_exactly_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def render_matches_reference(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def extent_matches_retained(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
