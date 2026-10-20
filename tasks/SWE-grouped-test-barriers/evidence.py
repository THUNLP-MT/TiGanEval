'Owner persona, belief, and factual Observation contexts for this task.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dilara, who runs the device lab and its overnight test benches. She reads "
    "the morning report, the console log a recorded night prints, and the board "
    "that says which handsets are booked out; she does not read the runner's code."
)

USER_BELIEF = (
    "I want the handover suite to be worth the chamber time it costs. It has "
    "been green since April and last week we worked out it has never once had "
    "two phones live at the same moment: the first handset works through the "
    "whole case and the second one starts afterwards, so the overlap the case "
    "exists to measure has never happened. Firmware sign-off leans on those "
    "green results and the drop is three weeks out. The other half of it is the "
    "morning report. That report is how the lab decides which unit goes back to "
    "the vendor and which bug gets filed, and it has to say what each handset on "
    "a bench actually did, with that handset's own faults against its own name. "
    "What I can see is the report, the console log of a night, and the pool "
    "board. Done, for me, is a fortnight of nights where the phones on a bench "
    "work a case together, the report tells me which phone to pull, and the "
    "chamber is open and the fleet is back on charge when I come in."
)

OBSERVATION_SCENE = "The lab lead's eight o'clock read of the morning report and the night's console log"


DID_NOT_RUN = observation(
    first=(
        "The measured night ended through an error instead of returning cleanly, "
        "so I cannot treat that run as a completed result."
    ),
    second=(
        "I repeated the measured session and it again failed to return cleanly. "
        "The runner ended with: {error}."
    ),
    detail="{error}",
)

CASE_NOT_RUN = observation(
    first="A morning-report row has no matching case execution in the console log.",
    second=(
        "The report contains {case} for {handset} on {bench}, but the trace has no "
        "case step for that same execution."
    ),
    detail="{handset}",
)

ROW_WRONG_BENCH = observation(
    first=(
        "A morning-report row names a different bench from the session entry for "
        "that handset and case."
    ),
    second=(
        "For {case}, {handset}'s row says {written}; the expected bench is "
        "{expected}."
    ),
    detail="{written}",
)

ROW_MISSING = observation(
    first=(
        "The morning report is missing one of the handset rows expected for a "
        "case on a bench that ran."
    ),
    second=(
        "There is no row for {handset} in {case} on {bench}; that bench has "
        "{expected_rows} participating handsets."
    ),
    detail="{handset}",
)

ROW_DUPLICATED = observation(
    first=(
        "The morning report contains more than one row for the same handset in "
        "the same case and bench."
    ),
    second="For {case} on {bench}, {handset} has {found} report rows.",
    detail="{found}",
)

ROW_UNEXPECTED = observation(
    first=(
        "The morning report contains a case-and-handset row outside the expected "
        "records for the measured night."
    ),
    second=(
        "The report contains {found} row(s) for {handset} in {case} on {bench}, "
        "where no such row is expected."
    ),
    detail="{bench}",
)

FLAG_WRONG_ROW = observation(
    first=(
        "A flag written by one handset execution appears on another handset's "
        "report row."
    ),
    second=(
        "In {case}, `{flag}` belongs to {handset} on {bench}, but it is written "
        "on {written_to}'s row."
    ),
    detail="{written_to}",
)

FLAG_REPEATED = observation(
    first="One expected flag appears more than once among the report's flag entries.",
    second=(
        "In {case}, `{flag}` from {handset} appears {rows} times among the "
        "report's flag entries."
    ),
    detail="{rows}",
)

FLAG_MISSING = observation(
    first="A flag expected from a handset execution is absent from every report row.",
    second="In {case}, `{flag}` from {handset} appears on no report row.",
    detail="{handset}",
)

FLAG_UNEXPECTED = observation(
    first=(
        "A morning-report row contains a flag that the measured case did not "
        "assign to that execution."
    ),
    second=(
        "The row for {handset} in {case} on {bench} contains the unexpected flag "
        "`{flag}`."
    ),
    detail="{flag}",
)

OUTCOME_MISMATCH = observation(
    first=(
        "A morning-report outcome differs from the outcome implied by the "
        "measured execution."
    ),
    second=(
        "For {handset} in {case} on {bench}, the report says {written}; the "
        "expected outcome is {expected}."
    ),
    detail="{written}",
)

GATE_RELEASE_MISMATCH = observation(
    first=(
        "The handsets recorded before the first resume from a named point do "
        "not match that meeting's expected participants."
    ),
    second=(
        "At `{gate}` during {scope} on {bench}, the console recorded {arrived} "
        "arrival(s) before the first resume: {arrived_handsets}. The expected "
        "{party} participant(s) are: {expected_handsets}."
    ),
    detail="{arrived_handsets}",
)

CASE_WAITERS_REMAIN = observation(
    first="The console has arrivals at a case gate without matching resumes.",
    second=(
        "At `{gate}` in {case} on {bench}, {arrived} arrivals produced "
        "{waiting} unmatched arrival(s); the expected party is {party}."
    ),
    detail="{waiting}",
)

BENCH_GATE_INCOMPLETE = observation(
    first=(
        "A bench-wide phase did not complete its expected single-party gate "
        "exchange."
    ),
    second=(
        "During {phase} on {bench}, `{gate}` has {arrived} arrival(s) and no "
        "complete gate exchange."
    ),
    detail="{phase}",
)

CASE_PARTY_MISMATCH = observation(
    first=(
        "The distinct handsets arriving at a case meeting do not match the "
        "handsets expected from that session bench."
    ),
    second=(
        "At `{gate}` in {case} on {bench}, {arrived} distinct handset(s) arrived; "
        "the session bench requires {party}."
    ),
    detail="{arrived}",
)

BENCH_PHASE_MULTIPLE_DRIVERS = observation(
    first=(
        "A bench-wide phase is attributed to more than one participating handset "
        "in the console trace."
    ),
    second=(
        "On {bench}, {phase} is attributed to {runs} distinct handsets: "
        "{handsets}."
    ),
    detail="{runs}",
)

BENCH_PHASE_RUN_COUNT = observation(
    first="A bench-wide phase did not start exactly once in the console trace.",
    second=(
        "On {bench}, {phase} has {runs} recorded start(s); its recorded driver "
        "set is {handsets}."
    ),
    detail="{runs}",
)

CONTEXT_OUTSIDE = observation(
    first=(
        "A context question returned a handset value during a phase that has no "
        "handset binding."
    ),
    second=(
        "During {phase}, `{field}` returned {answered} instead of refusing the "
        "unbound request."
    ),
    detail="{answered}",
)

CONTEXT_WRONG_ERROR = observation(
    first=(
        "An unbound context question raised a different error type from the "
        "frozen protocol."
    ),
    second=(
        "During {phase}, `{field}` raised {raised}; the protocol requires "
        "{expected}."
    ),
    detail="{raised}",
)

ALERT_DETAILS_MISSING = observation(
    first=(
        "A protocol error has the expected type but does not carry all required "
        "detail fields."
    ),
    second=(
        "During {phase}, the error for `{asked_for}` was {raised} and carried "
        "{said}."
    ),
    detail="{said}",
)

GATE_OUTSIDE_PHASE = observation(
    first=(
        "A named-point request from a phase without a handset binding did not "
        "match the frozen protocol response."
    ),
    second=(
        "During {phase}, `{gate}` produced {raised}; the protocol requires "
        "{expected}."
    ),
    detail="{gate}",
)

TIMEOUT_TYPE_MISMATCH = observation(
    first=(
        "A negative or zero gate timeout produced a different error type from "
        "the distinct type required for that value by the frozen protocol."
    ),
    second=(
        "During {phase}, `{gate}` with timeout {timeout} produced {raised}; the "
        "protocol requires {expected}."
    ),
    detail="{timeout}",
)

WRONG_HANDSET_CONTEXT = observation(
    first=(
        "A handset-bound phase returned a handset different from the execution "
        "recorded on that trace row."
    ),
    second=(
        "During {scope}, the execution asked for `{field}` and received "
        "{answered}."
    ),
    detail="{answered}",
)

MISSING_HANDSET_CONTEXT = observation(
    first=(
        "A handset-bound phase raised instead of returning its execution's "
        "handset context."
    ),
    second=(
        "During {scope}, the execution asked for `{field}` and raised {raised}."
    ),
    detail="{raised}",
)

PROBE_MISSING = observation(
    first="An expected conformance probe is absent from the console trace.",
    second=(
        "The `{asked_for}` probe at index {index} of {scope} is missing."
    ),
    detail="{asked_for}",
)

TURN_LIMIT = observation(
    first="The scheduler reported that it reached its turn limit.",
    second=(
        "The measured run stopped after {turns} scheduler turns with the limit "
        "marked exhausted."
    ),
    detail="{turns}",
)

UNFINISHED_WORK = observation(
    first="The night reached quiescence with at least one unfinished fiber.",
    second=(
        "The report lists {unfinished} unfinished fiber(s); the first is {fiber}, "
        "waiting for {waiting_for}."
    ),
    detail="{unfinished}",
)

LAB_CLOSE_MISSING = observation(
    first="The console trace contains no recorded start of the lab closing phase.",
    second=(
        "No lab-close start appears after {benches_run} of {benches_expected} "
        "session benches appeared in the trace; the last was {stopped_after}."
    ),
    detail="{stopped_after}",
)

BENCHES_MISSING = observation(
    first="One or more session benches have no trace row in the measured night.",
    second=(
        "The trace is missing {skipped} session bench(es): {skipped_benches}. "
        "The last bench that does appear is {bench}."
    ),
    detail="{skipped_benches}",
)

BENCH_CLOSE_MISSING = observation(
    first="A bench that appears in the night has no bench-closing trace row.",
    second=(
        "The trace contains work for {bench}, whose session handsets are "
        "{handsets}, but contains no bench-close row for it."
    ),
    detail="{bench}",
)

HANDSETS_HELD = observation(
    first=(
        "The final pool state still lists one or more session handsets as checked "
        "out."
    ),
    second=(
        "The final pool state lists {held} held handset(s): {handsets}; the first "
        "listed handset belongs to {bench}."
    ),
    detail="{held}",
)

POOL_SEQUENCE = observation(
    first=(
        "A session handset's pool events are not exactly one checkout followed by "
        "one release."
    ),
    second="For {handset} on {bench}, the recorded pool event sequence is {events}.",
    detail="{events}",
)

LAB_OPEN_ORDER = observation(
    first=(
        "At least one bench trace row appears before the first recorded lab-open "
        "start."
    ),
    second=(
        "The first such bench is {first_bench}; {benches_before_opening} bench(es) "
        "appear before lab opening, and {openings} lab-open start(s) were recorded."
    ),
    detail="{first_bench}",
)

LAB_PHASE_COUNT = observation(
    first="A session-wide lab phase has more than one recorded start.",
    second=(
        "Across {benches_run} reached benches, {phase} has {runs} recorded starts."
    ),
    detail="{runs}",
)


OBSERVATIONS = {
    "record_attribution": {
        "candidate_execution_failed": DID_NOT_RUN,
        "case_not_run_for_handset": CASE_NOT_RUN,
        "row_on_wrong_bench": ROW_WRONG_BENCH,
        "no_row_for_a_handset": ROW_MISSING,
        "two_rows_for_one_handset": ROW_DUPLICATED,
        "row_for_a_case_the_bench_did_not_run": ROW_UNEXPECTED,
        "flag_landed_on_another_handset": FLAG_WRONG_ROW,
        "flag_landed_on_several_records": FLAG_REPEATED,
        "flag_lost_between_records": FLAG_MISSING,
        "unexpected_flag_on_report": FLAG_UNEXPECTED,
        "wrong_case_outcome": OUTCOME_MISMATCH,
    },
    "gate_scope_and_lifetime": {
        "candidate_execution_failed": DID_NOT_RUN,
        "gate_did_not_hold": GATE_RELEASE_MISMATCH,
        "gate_reused_inside_the_case": GATE_RELEASE_MISMATCH,
        "gate_reused_across_the_night": GATE_RELEASE_MISMATCH,
    },
    "gate_party_from_bench": {
        "candidate_execution_failed": DID_NOT_RUN,
        "handsets_left_waiting": CASE_WAITERS_REMAIN,
        "bench_gate_blocked": BENCH_GATE_INCOMPLETE,
        "bench_did_not_all_meet": CASE_PARTY_MISMATCH,
        "bench_phase_ran_on_every_handset": BENCH_PHASE_MULTIPLE_DRIVERS,
        "bench_phase_run_count_wrong": BENCH_PHASE_RUN_COUNT,
    },
    "context_binding_contract": {
        "candidate_execution_failed": DID_NOT_RUN,
        "context_answered_outside_its_phase": CONTEXT_OUTSIDE,
        "context_alert_was_the_wrong_kind": CONTEXT_WRONG_ERROR,
        "alert_missing_its_details": ALERT_DETAILS_MISSING,
        "wrong_handset_reported": WRONG_HANDSET_CONTEXT,
        "no_handset_reported_inside_its_phase": MISSING_HANDSET_CONTEXT,
        "gate_request_outside_its_phase": GATE_OUTSIDE_PHASE,
        "timeout_sign_not_told_apart": TIMEOUT_TYPE_MISMATCH,
        "probe_not_run": PROBE_MISSING,
    },
    "night_envelope": {
        "candidate_execution_failed": DID_NOT_RUN,
        "scheduler_turn_limit_exhausted": TURN_LIMIT,
        "night_left_unfinished_work": UNFINISHED_WORK,
        "night_never_closed": LAB_CLOSE_MISSING,
        "benches_after_a_failure_never_ran": BENCHES_MISSING,
        "bench_close_skipped": BENCH_CLOSE_MISSING,
        "handsets_left_checked_out": HANDSETS_HELD,
        "pool_event_order_wrong": POOL_SEQUENCE,
        "night_opened_out_of_turn": LAB_OPEN_ORDER,
        "night_phase_ran_twice": LAB_PHASE_COUNT,
    },
}
