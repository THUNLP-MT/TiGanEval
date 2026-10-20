'Owner persona, belief, and Observation contexts for SWE-publish-retry-audit.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Tereza, release manager for the toolchain. She reads the summary a release "
    "job prints, the vendor's own log when she opens a ticket with them, and "
    "the download page itself; she does not read the publishing step's code."
)

USER_BELIEF = (
    "I want releases that go out without me sitting up with them. Tuesday's "
    "2.4.0 was the third this year I finished by hand at eleven at night: the "
    "upload host turned away the first two files the job handed it, the job "
    "dropped them and published the rest, and people downloaded a release page "
    "with half the files on it. What I can see is the summary the release job "
    "prints, the vendor's log when I open a ticket, and the page a user lands "
    "on. The support desk and the vendor's people read the same things I do, "
    "and they "
    "come back to me about them. Done, for me, is a quarter in which every "
    "release page is complete the first time, nobody is paged for something "
    "the release job did to itself, and when the host does misbehave I can "
    "hand the vendor an account of what we sent them that they will not argue "
    "with."
)

OBSERVATION_SCENE = "Release manager's review of a publish after a release has gone out"


DID_NOT_RUN = observation(
    first=(
        "The release review could not finish because one of the rehearsals "
        "stopped part way through. I cannot treat the result as a completed "
        "publish report."
    ),
    second=(
        "The console line from the rehearsal is: {error}. That run needs to "
        "complete before its release report can be reviewed."
    ),
    detail="{error}",
)

PUBLISHED_OBJECT_MISMATCH = observation(
    first=(
        "The objects left by the publish do not agree with the release plan. "
        "At least one publish destination cannot be reconciled with its "
        "build output."
    ),
    second=(
        "The first destination I could not reconcile is {target}. The replay "
        "shows the plan and the host state beside each other."
    ),
    detail="{target}",
)

LEDGER_COUNT_MISMATCH = observation(
    first=(
        "The vendor's call count and the attempts block do not reconcile for "
        "at least one destination."
    ),
    second=(
        "For {target}, their log contains {tries_the_host_logged} puts and our "
        "block contains {lines_in_the_block} lines."
    ),
    detail="{target}",
)

LEDGER_CONTENT_MISMATCH = observation(
    first=(
        "The attempts block and the host log count the same traffic at one "
        "destination, but their accounts of it do not agree."
    ),
    second=(
        "The disagreement is under {target}. Compare that destination's block "
        "lines with the corresponding puts in the replay."
    ),
    detail="{target}",
)

FINAL_ANSWER_RETRIED = observation(
    first=(
        "A destination was sent again after the host had already given a "
        "final answer about that publish."
    ),
    second=(
        "The host log shows {tries} sends to {target}; its first answer was: "
        "{host_said}."
    ),
    detail="{tries}",
)

RETRY_TOO_SOON = observation(
    first=(
        "At least one retry left sooner than the release timing allowed. The "
        "host log and the configured window do not agree on that gap."
    ),
    second=(
        "The measured gap before the retry to {target} was {waited_ms} ms. "
        "The replay prints the applicable host direction and release settings "
        "beside it."
    ),
    detail="{waited_ms}",
)


OBSERVATIONS = {
    "published_bytes_match_the_build": {
        "candidate_execution_failed": DID_NOT_RUN,
        "artifact_never_landed": PUBLISHED_OBJECT_MISMATCH,
        "stored_body_is_not_the_artifact": PUBLISHED_OBJECT_MISMATCH,
    },
    "attempt_ledger_matches_the_host_log": {
        "candidate_execution_failed": DID_NOT_RUN,
        "attempt_missing_from_the_ledger": LEDGER_COUNT_MISMATCH,
        "ledger_recorded_an_attempt_that_never_happened": LEDGER_COUNT_MISMATCH,
        "ledger_called_a_refused_attempt_a_success": LEDGER_CONTENT_MISMATCH,
        "attempt_numbers_do_not_match_the_tries": observation(
            first=(
                "The try numbers in the attempts block do not line up with "
                "the calls in the host log for one destination."
            ),
            second=(
                "For {target}, the block uses numbers {numbers} against "
                "{tries_the_host_logged} host calls."
            ),
            detail="{numbers}",
        ),
        "ledger_line_disagrees_with_host": LEDGER_CONTENT_MISMATCH,
    },
    "refusals_are_answered_not_retried": {
        "candidate_execution_failed": DID_NOT_RUN,
        "refusal_retried": FINAL_ANSWER_RETRIED,
        "mirror_answer_retried": FINAL_ANSWER_RETRIED,
        "transient_failure_abandoned": observation(
            first=(
                "A destination stopped after an answer the release tooling "
                "classifies as temporary, while retry budget remained."
            ),
            second=(
                "The first send to {target} came back {status}; the host log "
                "contains {tries} send and the settings allow "
                "{attempts_allowed}."
            ),
            detail="{status}",
        ),
        "host_message_replaced": observation(
            first=(
                "A permanent failure in the summary does not preserve the "
                "answer recorded by the host."
            ),
            second=(
                "For {target}, the host recorded {host_said}; the summary "
                "contains {summary_said}."
            ),
            detail="{summary_said}",
        ),
        "planned_item_was_skipped": observation(
            first=(
                "A destination present in the release plan has no matching "
                "send in a rehearsal that was not stopped."
            ),
            second=(
                "The unmatched plan destination is {target} at {instance}."
            ),
            detail="{target}",
        ),
    },
    "waits_follow_the_hosts_direction": {
        "candidate_execution_failed": DID_NOT_RUN,
        "retried_before_the_host_allowed_it": RETRY_TOO_SOON,
        "one_wait_ran_past_the_release_window": observation(
            first=(
                "One pause in the host log is longer than the release window "
                "allows for a single retry."
            ),
            second=(
                "The measured pause before retrying {target} is {waited_ms} ms; "
                "the configured cap is {max_delay_ms} ms."
            ),
            detail="{waited_ms}",
        ),
        "retried_without_the_configured_pause": RETRY_TOO_SOON,
        "kept_publishing_after_the_stop": observation(
            first=(
                "The host log contains traffic timestamped after the console's "
                "stop, so the stopped rehearsal did not stay quiet."
            ),
            second=(
                "I counted {calls_after_the_stop} calls to the host after the "
                "stop at {stopped_at_ms} ms, beginning with {target}. Stop has "
                "to mean that nothing else leaves for the host."
            ),
            detail="{calls_after_the_stop}",
        ),
    },
    "release_is_independent_of_publish_order": {
        "candidate_execution_failed": DID_NOT_RUN,
        "what_shipped_depends_on_the_order": observation(
            first=(
                "Two clean rehearsals of the same release, stopped after the "
                "same elapsed time, left different host state when only their "
                "build-finish order changed."
            ),
            second=(
                "The two host states contain {objects_first_run} and "
                "{objects_second_run} objects; their first measured difference "
                "is at {differs_at}."
            ),
            detail="{differs_at}",
        ),
        "ledger_order_follows_the_run": observation(
            first=(
                "The attempts block changes when the same clean rehearsal is "
                "given a different build-finish order."
            ),
            second=(
                "The two blocks first differ at line {first_difference}: one "
                "contains {line_first_run} there and the other contains "
                "{line_second_run}."
            ),
            detail="{first_difference}",
        ),
        "release_made_no_attempt_before_stop": observation(
            first=(
                "At least one clean rehearsal produced no sends before its "
                "elapsed-time stop, leaving an empty result to compare."
            ),
            second=(
                "Before their stop points, the two host logs contain "
                "{calls_first_run} and {calls_second_run} sends."
            ),
            detail="{calls_first_run}",
        ),
        "ledger_not_in_vendor_order": observation(
            first=(
                "An attempts block does not follow the ordering used by the "
                "reconciliation record."
            ),
            second=(
                "In {run}, the first misplaced entry is line "
                "{first_difference}: it contains {line_in_block}."
            ),
            detail="{first_difference}",
        ),
    },
}
