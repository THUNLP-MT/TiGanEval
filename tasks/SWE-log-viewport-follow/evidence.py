'Owner persona, belief, and Observation contexts for SWE-log-viewport-follow.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ines, on call for the incident console. She watches the pane on the wall, "
    "the Live/Paused badge above it and the session audit the toolbar keeps; she "
    "does not read the pane's code."
)

USER_BELIEF = (
    "I want a shift where I can read the console during a page instead of giving "
    "up and reading the raw file. When a worker logs a line I should still be "
    "looking at whatever I stopped on, and the badge above the pane should tell "
    "me whether I am watching the newest line or sitting still. Right now I lose "
    "my place every few seconds and the badge tells me nothing I can trust; "
    "during Tuesday's 03:10 page I gave up on the console, which is how we missed "
    "the carrier switch for four minutes. The shift leads read the same pane, and "
    "so does whoever writes the incident up afterwards off the session audit. "
    "Done, for me, is a night where nobody on call has to leave the console to "
    "find out what the workers are doing."
)

OBSERVATION_SCENE = "On-call's review of the incident console after a night shift"


DID_NOT_DRAW = observation(
    first=(
        "One of the console rehearsals stopped before its review completed, so I "
        "cannot treat that run as evidence about the pane."
    ),
    second=(
        "The console line from the stopped rehearsal is: {error}. That session "
        "needs to finish before its pane can be reviewed."
    ),
    detail="{error}",
)

ANCHOR_POSITION_MISMATCH = observation(
    first=(
        "While the reader was paused, a log or layout event left the viewport at a "
        "different position from the console's reading-place rule."
    ),
    second=(
        "The first mismatch begins with {top_before} at the top and occurs at "
        "{label}. Afterwards {top_after} is at the top, and the final position is "
        "{rows_moved} rows from the position described by the rule."
    ),
    detail="{rows_moved}",
)

BADGE_POSITION_MISMATCH = observation(
    first=(
        "The Live/Paused badge does not agree with the viewport's actual position "
        "for one event in the session."
    ),
    second=(
        "At {label}, the badge is {badge}; the pane reports position "
        "{reported_scroll_y} against a last valid top position of "
        "{expected_max_scroll_y}."
    ),
    detail="{badge}",
)

SCROLLBAR_POSITION_MISMATCH = observation(
    first=(
        "The vertical scrollbar's position or end stop does not agree with the rows "
        "drawn on the pane."
    ),
    second=(
        "At {label}, the drawn rows put the last valid top at "
        "{expected_max_scroll_y}; the pane reports an end stop of "
        "{reported_max_scroll_y} and a position of {reported_scroll_y}."
    ),
    detail="{reported_max_scroll_y}",
)

AUDIT_OUTCOME_MISMATCH = observation(
    first=(
        "For one event, the badge transition, the pane's settled state and the "
        "records posted to the session audit do not reconcile."
    ),
    second=(
        "At {label}, the badge goes from {badge_before} to {badge_after} and the "
        "toolbar posts {records_here} audit records. Compare those records with the "
        "settled pane shown by the replay."
    ),
    detail="{records_here}",
)

RETAINED_ENTRIES_MISMATCH = observation(
    first=(
        "The ordered worker entries retained by the pane do not agree with the "
        "writes, clear and configured entry cap in the session."
    ),
    second=(
        "After {label}, the first difference is position {first_difference}: the "
        "session calls for {expected_entry} there and the pane has {pane_entry}. "
        "Their entry counts are {expected_entry_count} and {pane_entry_count}."
    ),
    detail="{first_difference}",
)

ENTRY_DRAWING_MISMATCH = observation(
    first=(
        "An entry drawn on the pane does not agree with the console's shared "
        "rendering contract at the current layout."
    ),
    second=(
        "The first mismatch is {entry} after {label}, at pane width {width} and "
        "reading minimum {min_width}. The pane and exporter first differ at row "
        "{first_row_that_differs}."
    ),
    detail="{first_row_that_differs}",
)

EXTENT_MISMATCH = observation(
    first=(
        "The extent reported to the scrollbars does not agree with the lines the "
        "pane is currently drawing."
    ),
    second=(
        "At {label}, the pane reports width {reported_width} and "
        "{reported_lines} rows; its drawn lines measure {actual_width} columns and "
        "{rows_on_the_pane} rows."
    ),
    detail="{label}",
)


OBSERVATIONS = {
    "paused_anchor_holds": {
        "candidate_execution_failed": DID_NOT_DRAW,
        "paused_view_jumped_to_the_end": ANCHOR_POSITION_MISMATCH,
        "paused_view_slid_under_prune": ANCHOR_POSITION_MISMATCH,
        "paused_view_slid_after_reflow": ANCHOR_POSITION_MISMATCH,
        "paused_view_slid_after_the_reading_minimum": ANCHOR_POSITION_MISMATCH,
        "paused_view_lost_the_row_on_an_unchanged_entry": ANCHOR_POSITION_MISMATCH,
    },
    "liveness_follows_position": {
        "candidate_execution_failed": DID_NOT_DRAW,
        "badge_live_while_scrolled_up": BADGE_POSITION_MISMATCH,
        "badge_paused_at_the_end": BADGE_POSITION_MISMATCH,
        "vertical_scrollbar_disagrees_with_pane": SCROLLBAR_POSITION_MISMATCH,
    },
    "follow_transitions_exactly_once": {
        "candidate_execution_failed": DID_NOT_DRAW,
        "record_posted_without_a_flip": AUDIT_OUTCOME_MISMATCH,
        "transition_not_posted": AUDIT_OUTCOME_MISMATCH,
        "record_carried_unsettled_position": AUDIT_OUTCOME_MISMATCH,
    },
    "render_matches_reference": {
        "candidate_execution_failed": DID_NOT_DRAW,
        "retained_entries_disagree": RETAINED_ENTRIES_MISMATCH,
        "deferred_entry_rendered_before_layout": ENTRY_DRAWING_MISMATCH,
        "full_width_entry_not_expanded": ENTRY_DRAWING_MISMATCH,
        "entry_kept_its_old_width": ENTRY_DRAWING_MISMATCH,
        "entry_ignored_the_reading_minimum": ENTRY_DRAWING_MISMATCH,
    },
    "extent_matches_retained": {
        "candidate_execution_failed": DID_NOT_DRAW,
        "content_width_kept_a_pruned_entry": EXTENT_MISMATCH,
        "content_width_stops_short_of_the_widest_line": EXTENT_MISMATCH,
        "line_count_disagrees_with_the_pane": EXTENT_MISMATCH,
    },
}
