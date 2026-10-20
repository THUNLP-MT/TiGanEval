"The five binary project rubrics for the catalogue listing endpoint."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "page_order_matches_catalogue": (
        "candidate_execution_failed",
        "products_missing_from_the_list",
        "products_repeated_in_the_list",
        "list_not_in_the_order_asked_for",
        "request_without_a_sort_served",
        "offset_page_served_the_wrong_products",
    ),
    "scroll_delivers_each_row_once": (
        "candidate_execution_failed",
        "product_delivered_twice_in_one_scroll",
        "product_present_throughout_never_reached",
        "restocked_product_never_reached",
    ),
    "cursor_refusal_contract": (
        "candidate_execution_failed",
        "own_cursor_not_honoured",
        "cursor_from_another_sort_honoured",
        "unreadable_cursor_not_refused",
        "edited_cursor_honoured",
        "cursor_without_a_sort_served",
        "cursor_with_an_offset_served",
    ),
    "page_boundary_honesty": (
        "candidate_execution_failed",
        "list_ended_while_products_remained",
        "continuation_offered_on_a_finished_list",
        "page_larger_than_the_service_serves",
        "page_shorter_than_the_size_asked_for",
    ),
    "cursor_is_self_contained": (
        "candidate_execution_failed",
        "second_instance_returned_a_different_page",
        "cursor_not_recognised_after_a_restart",
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


def page_order_matches_catalogue(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def scroll_delivers_each_row_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def cursor_refusal_contract(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def page_boundary_honesty(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def cursor_is_self_contained(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
