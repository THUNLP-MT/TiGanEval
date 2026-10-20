"""Five equal, binary outcome projections of one sandboxed workload."""

from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES = {
    "active_document_commands": (
        "candidate_execution_failed",
        "command_changed_another_document",
        "command_effect_not_conserved",
    ),
    "selection_survives_toolbar_focus": (
        "candidate_execution_failed",
        "selected_text_changed_differently",
        "toolbar_lost_the_edit_range",
    ),
    "theme_tracks_editor_context": (
        "candidate_execution_failed",
        "image_not_inserted",
        "unsupported_image_was_inserted",
        "image_delivered_to_stale_context",
        "image_chooser_unavailable",
        "image_chooser_kept_old_configuration",
        "link_input_unavailable",
        "link_dialog_opened_in_another_field",
        "format_display_described_another_field",
    ),
    "unavailable_context_is_inert": (
        "candidate_execution_failed",
        "unavailable_field_was_edited",
        "unavailable_field_opened_a_dialog",
        "controls_did_not_recover",
        "availability_display_was_stale",
        "unowned_toolbar_retained_style",
    ),
    "shared_control_lifecycle": (
        "candidate_execution_failed",
        "shared_surface_accumulated_widgets",
        "shared_surface_missing_component",
        "dynamic_control_did_not_act",
        "dynamic_control_repeated_action",
        "dynamic_control_used_stale_context",
    ),
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority={key: modes[1:] for key, modes in FAILURE_MODES.items()},
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def active_document_commands(artifact_dir, context):
    return RUBRICS.evaluate(artifact_dir, context)


def selection_survives_toolbar_focus(artifact_dir, context):
    return RUBRICS.evaluate(artifact_dir, context)


def theme_tracks_editor_context(artifact_dir, context):
    return RUBRICS.evaluate(artifact_dir, context)


def unavailable_context_is_inert(artifact_dir, context):
    return RUBRICS.evaluate(artifact_dir, context)


def shared_control_lifecycle(artifact_dir, context):
    return RUBRICS.evaluate(artifact_dir, context)
