'Owner persona, belief, and Observation contexts for SWE-persisted-query-restore.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Rana, who leads the front end of the Kerbside field app. She reads what the "
    "crews send her -- screenshots, the handset's diagnostics screen, the weekly "
    "signal figure the depot plans around -- and what a replay of a recorded "
    "session prints; she judges a change by those and not by reading the restore "
    "path back."
)

USER_BELIEF = (
    "I want a month in which a crew can shut the app, drive through a cutting, "
    "open it again and carry on from the screen they had. The vans lose signal "
    "for most of an hour at a time and the app is the only record of what has "
    "been read and what the depot has refused, so a screen that comes back "
    "wrong is a reading sent twice, an address worked in the wrong order, or a "
    "refusal nobody sees until the shift is over. What I get to see is what the "
    "crews send me: a screenshot of what came up, the diagnostics screen behind "
    "it, and the console log when I replay one of the recorded sessions. Done, "
    "for me, is a fortnight of poor signal in which nobody rings the desk about "
    "a screen that came back looking like something it is not, and the depot "
    "can trust the figure it plans the next day's rounds from."
)

OBSERVATION_SCENE = (
    "Rana's Friday look at the crews' screenshots and the console log after a week on the vans"
)


DID_NOT_RUN = observation(
    first=(
        "The bench replay stopped before the recorded session reached its end. "
        "It did not leave a complete operation and screen log for me to review."
    ),
    second=(
        "The replay stopped again. The final console line is: {error}. I need a "
        "session that reaches its end before I can compare the recorded screens."
    ),
    detail="{error}",
)


FELL_OVER = observation(
    first=(
        "A recorded operation ended with an exception instead of completing "
        "normally, so the replay does not contain a usable result for that step."
    ),
    second=(
        "The failing operation is {where}. Its console line is: {error}."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "restored_screen_fidelity": {
        "candidate_execution_failed": DID_NOT_RUN,
        "the_app_fell_over_on_a_screen": FELL_OVER,
        "restored_error_dropped": observation(
            first=(
                "The device copy contains error text, but the screen recorded "
                "after reopening contains no error text."
            ),
            second=(
                "For {key}, the device copy says {saved_reason} and has retry "
                "count {saved_failure_count}; the reopened screen has no error text."
            ),
            detail="{saved_reason}",
        ),
        "restored_status_contradicts_the_screen": observation(
            first=(
                "The device copy contains no error, but the reopened screen sets "
                "its error-banner field."
            ),
            second=(
                "For {key}, the saved data and error do not support an error "
                "banner, but the reopened screen reports one."
            ),
            detail="{key}",
        ),
        "restored_banner_is_missing": observation(
            first=(
                "The reopened screen contains error text but its error-banner "
                "field is not set."
            ),
            second=(
                "For {key}, the restored error text is {saved_reason}, while the "
                "screen records no error banner."
            ),
            detail="{saved_reason}",
        ),
        "restored_pages_dropped": observation(
            first=(
                "The device copy and the reopened screen contain different "
                "numbers of saved page cursors."
            ),
            second=(
                "The device copy has {saved_pages} page cursors and the reopened "
                "screen has {shown_pages}."
            ),
            detail="{saved_pages}",
        ),
        "restored_screen_is_a_fresh_load": observation(
            first=(
                "The last-updated value on the reopened screen differs from the "
                "value stored in the device copy."
            ),
            second=(
                "The device copy is stamped {saved_at}; the reopened screen is "
                "stamped {shown_at}."
            ),
            detail="{saved_at}",
        ),
        "restored_screen_is_not_the_copy_the_crew_left": observation(
            first=(
                "A field on the reopened screen differs from the screen derived "
                "from the device copy."
            ),
            second=(
                "For {key}, the first recorded difference is {field_name}."
            ),
            detail="{field_name}",
        ),
        "saved_screen_did_not_survive_restart": observation(
            first=(
                "The screen recorded immediately before the background save and "
                "the same query's screen after reopening the app do not match."
            ),
            second=(
                "For {key}, the first difference across the save and process "
                "restart is {field_name}; the last-updated values are {before_at} "
                "before and {after_at} after."
            ),
            detail="{field_name}",
        ),
    },
    "restore_load_accounting": {
        "candidate_execution_failed": DID_NOT_RUN,
        "the_app_fell_over_on_a_screen": FELL_OVER,
        "restore_counted_as_a_load": observation(
            first=(
                "At an operation or at the session total, the replay records "
                "more completed loads than depot calls."
            ),
            second=(
                "At {op_label}, the completed-load count increased by {loads_here} "
                "while the depot-call count increased by {depot_here}."
            ),
            detail="{loads_here}",
        ),
        "completed_load_went_missing": observation(
            first=(
                "At an operation or at the session total, the replay records "
                "fewer completed loads than depot calls."
            ),
            second=(
                "At {op_label}, the depot-call count increased by {depot_here} "
                "while the completed-load count increased by {loads_here}."
            ),
            detail="{depot_here}",
        ),
    },
    "restored_query_quiescence": {
        "candidate_execution_failed": DID_NOT_RUN,
        "the_app_fell_over_on_a_screen": FELL_OVER,
        "restored_screen_shows_a_load_that_is_not_running": observation(
            first=(
                "A writer-phase restore finished with no screen recorded or with "
                "the restored screen's spinner still set."
            ),
            second=(
                "For {key}, the device copy's loading state is {saved_fetch_state}; "
                "the returned screen's loading state is {shown_fetch_status}, and "
                "the replay records {depot_calls_for_key} depot calls for that query."
            ),
            detail="{shown_fetch_status}",
        ),
        "rebuild_left_a_finished_load_running": observation(
            first=(
                "After a rebuild operation returned, at least one restored query "
                "still had a non-idle loading state."
            ),
            second=(
                "For {key}, the loading state immediately after rebuild is "
                "{shown_fetch_status}."
            ),
            detail="{shown_fetch_status}",
        ),
        "restored_screen_varies_with_what_the_writer_caught": observation(
            first=(
                "Saved query fixtures with otherwise identical state but different "
                "recorded loading states restore to different screens."
            ),
            second=(
                "The copies for {key} and {other_key} record loading states "
                "{saved_fetch_state} and {other_fetch_state}; their restored "
                "screens first differ at {field_name}."
            ),
            detail="{field_name}",
        ),
    },
    "restore_path_agreement": {
        "candidate_execution_failed": DID_NOT_RUN,
        "the_app_fell_over_on_a_screen": FELL_OVER,
        "rebuild_dropped_the_error": observation(
            first=(
                "For the same device copy, the cold-start rebuild screen has no "
                "error text while the direct-restore screen does."
            ),
            second=(
                "For {key}, direct restore shows {saved_reason}; cold-start rebuild "
                "records no error text."
            ),
            detail="{saved_reason}",
        ),
        "the_two_ways_in_disagree": observation(
            first=(
                "The cold-start rebuild and direct restore produce different "
                "screen fields for the same device copy."
            ),
            second=(
                "For {key}, the first field that differs between the two paths is "
                "{field_name}."
            ),
            detail="{field_name}",
        ),
    },
    "rebuild_freshness_merge": {
        "candidate_execution_failed": DID_NOT_RUN,
        "the_app_fell_over_on_a_screen": FELL_OVER,
        "rebuild_overwrote_newer_rows": observation(
            first=(
                "After rebuild, the screen's row timestamp is older than the row "
                "timestamp the live process held before rebuild."
            ),
            second=(
                "For {key}, the live row timestamp is {live_at}; after rebuild the "
                "screen records {shown_at}."
            ),
            detail="{live_at}",
        ),
        "rebuild_skipped_the_saved_error": observation(
            first=(
                "The device holds the newer error state, but the screen recorded "
                "after rebuild contains no error text."
            ),
            second=(
                "For {key}, the device error is {saved_reason} at "
                "{saved_error_at}; the rebuilt screen has no error text."
            ),
            detail="{saved_reason}",
        ),
        "rebuild_merged_without_the_banner": observation(
            first=(
                "The rebuilt screen contains the expected rows and error text, "
                "but its error-banner field is not set."
            ),
            second=(
                "For {key}, the rebuilt screen contains {saved_reason} and the "
                "expected rows, but records no error banner."
            ),
            detail="{key}",
        ),
        "rebuild_left_the_screen_between_the_two": observation(
            first=(
                "A field on the rebuilt screen does not match the newer saved "
                "or live state selected separately for that field group."
            ),
            second=(
                "For {key}, the first field inconsistent with the newer recorded "
                "state is {field_name}."
            ),
            detail="{field_name}",
        ),
    },
}
