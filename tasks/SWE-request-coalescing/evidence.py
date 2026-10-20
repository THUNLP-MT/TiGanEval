'The owner of the summary relay, and what she reports seeing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Halima, who leads the backend team behind the document summarisation "
    "service; she reads the incident channel, the replay of a recorded window, "
    "the usage ledger finance sends her, and the tickets customers open, and "
    "she does not work in the relay's code."
)

USER_BELIEF = """What I want is for the relay to stop asking the backend for the same thing many times over. When a row of desks lands on one document inside a couple of seconds, that should cost the backend one rendering, and every one of those desks should still come away with its summary. Friday's invoice run is the shape of the problem: the backend shed load for everybody, checkout included, because we hammered it with the same request. The desks are the customers who pay us, and I am not willing to buy the backend's headroom with a pile of tickets from them. Done is a month of invoice runs where the backend stays up and no desk opens a ticket about the summary it got."""

OBSERVATION_SCENE = "Summary relay incident review"


_DID_NOT_RUN = observation(
    first=(
        "I could not get a complete replay out of the relay. Without a usable "
        "hour I cannot account for which calls reached the backend or which "
        "desks received an answer."
    ),
    second=(
        "I replayed the hour with your build in the tree and it did not produce "
        "a complete usable measurement. The replay reports `{error}`; until it "
        "finishes, none of the hour's outcomes can be reconciled."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "delivered_response_equivalence": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "response_from_another_scope": observation(
            first=(
                "Compliance found a desk reading a summary rendered for a "
                "different access scope. The backend redacts each rendering "
                "for its scope, so sharing those two copies can disclose text "
                "or hide text that caller should have received."
            ),
            second=(
                "I put the same hour through your build and looked at what that "
                "desk was handed: it is the summary the backend renders for "
                "{scope_the_summary_came_from}, and not the one that account "
                "reads in. "
                "Sharing a rendering is only safe while the desks cannot tell."
            ),
            detail="{scope_the_summary_came_from}",
        ),
        "refusal_not_delivered_to_unauthorized_caller": observation(
            first=(
                "A caller that the directory does not authorize for its "
                "requested document was handed a summary instead of being "
                "refused. That is a document disclosure, regardless of whether "
                "the account was never granted access or was later removed."
            ),
            second=(
                "I ran the hour again on your build and traced the account: "
                "the directory did not authorize {principal} for the requested "
                "document, but the call was answered with a summary anyway."
            ),
            detail="{principal}",
        ),
        "summary_after_the_rendering_failed": observation(
            first=(
                "At least one caller whose request was in flight when the "
                "backend reported failure received a summary instead of a "
                "failure outcome. The replay does not establish which "
                "internal path produced that summary."
            ),
            second=(
                "I replayed that hour on your build and followed the desks that "
                "were attached to the rendering for {document_id} when it died: "
                "this caller comes away with a summary rather than the failure "
                "outcome owed for that episode. The replay shows the mismatch, "
                "not which internal path supplied those summary bytes."
            ),
            detail="{document_id}",
        ),
        "response_missing_leading_chunks": observation(
            first=(
                "A desk received only a trailing part of its summary: the "
                "opening pieces are missing and the delivered text starts "
                "further into the backend's rendering."
            ),
            second=(
                "I replayed the hour on your build and counted what that desk "
                "was handed: {pieces_delivered} of the {pieces_in_the_summary} pieces the "
                "backend renders for that document. The missing ones are the "
                "leading pieces of that rendering."
            ),
            detail="{pieces_delivered}",
        ),
        "response_pieces_out_of_order": observation(
            first=(
                "A desk received all of the backend's summary pieces, but in a "
                "different order. The delivered text starts on a later piece "
                "instead of the backend's opening piece."
            ),
            second=(
                "I replayed that hour on your build and read the summary that "
                "desk was handed against what the backend renders for it. Every "
                "piece is there, and it opens on the piece the backend renders "
                "in position {opening_piece_position} of "
                "{pieces_in_the_summary}. They are in an order of their own, "
                "not the order the backend puts them in."
            ),
            detail="{opening_piece_position}",
        ),
        "refusal_instead_of_the_summary": observation(
            first=(
                "A caller that should have received its document summary was "
                "given a refusal instead. The refusal is the caller's final "
                "answer even though its requested rendering was expected to "
                "complete."
            ),
            second=(
                "I replayed that hour on your build and read what that desk was "
                "told: `{reason}`, when the rendering for that caller was "
                "expected to complete."
            ),
            detail="{reason}",
        ),
        "response_did_not_match_reference": observation(
            first=(
                "A desk received text that cannot be reconciled with the "
                "backend's rendering for its requested document and access "
                "scope. It is neither the expected summary nor a recognized "
                "scope-specific copy."
            ),
            second=(
                "I ran the hour again on your build and pulled that call: "
                "{call_id} was handed text that is not what the backend renders "
                "for that document and that desk, so there is nothing to "
                "reconcile it against."
            ),
            detail="{call_id}",
        ),
    },
    "every_call_answered_once": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "waiters_unresolved_after_the_backend_failed": observation(
            first=(
                "At least one accepted call in an in-flight episode whose "
                "matching rendering the backend marked failed was left "
                "waiting with no summary and no refusal."
            ),
            second=(
                "I replayed that hour on your build and went through the desks "
                "that never heard anything back, and the tally is "
                "{callers_left_waiting} calls still sitting open when the hour "
                "ends. This unanswered call belongs to an in-flight episode "
                "whose matching rendering the backend marked failed."
            ),
            detail="{callers_left_waiting}",
        ),
        "waiters_unresolved_after_the_first_caller_left": observation(
            first=(
                "A caller left during a window with work still in flight, and "
                "at least one other accepted call in that window ended without "
                "a summary or a refusal. A caller walking away must not strand "
                "connections that remain open."
            ),
            second=(
                "I ran that hour again on your build and watched the desks on "
                "{document_id}: that call remains unanswered in a window where "
                "another caller left while work was in flight. The remaining "
                "open calls still need their own outcome."
            ),
            detail="{document_id}",
        ),
        "desk_the_directory_dropped_left_unanswered": observation(
            first=(
                "A customer removed a desk from the directory while its client "
                "could still call the front door. One such accepted call was "
                "left open with no summary and no refusal."
            ),
            second=(
                "I ran the hour again on your build and found the account: "
                "{principal} is not in the directory any more, and this call "
                "went into the relay without an answer coming back out. The "
                "front door is still holding that connection open."
            ),
            detail="{principal}",
        ),
        "call_left_unanswered": observation(
            first=(
                "At least one accepted call ended with nothing back at all, "
                "neither a summary nor a refusal. The caller cannot tell "
                "whether its request completed or whether it should try again."
            ),
            second=(
                "I replayed the hour on your build and went through the calls "
                "that end with nothing: the tally is {callers_left_waiting} "
                "taken in at the front door and never answered. A call we "
                "accept is a call we owe an answer to."
            ),
            detail="{callers_left_waiting}",
        ),
        "call_answered_twice": observation(
            first=(
                "One accepted call received more than one outcome. Those "
                "outcomes may agree or conflict, but the caller cannot receive "
                "two final answers for one request."
            ),
            second=(
                "I replayed the hour on your build and pulled that call: the "
                "relay answers it {answers} times. One caller is one answer, "
                "whether the work behind it was shared or not."
            ),
            detail="{answers}",
        ),
    },
    "upstream_execution_conservation": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "duplicate_upstream_executions": observation(
            first=(
                "A set of callers that could share one in-flight rendering "
                "caused the backend to start more than one. Those extra "
                "renderings remove the capacity saving this relay is meant to "
                "provide."
            ),
            second=(
                "I replayed that hour on your build and counted what the "
                "backend was asked for: {executions} renderings of one document "
                "in a window where those desks were all asking at once. That is "
                "the bill we pay and the load that tips the backend over."
            ),
            detail="{executions}",
        ),
        "upstream_execution_without_a_caller": observation(
            first=(
                "The backend request log contains rendering work that cannot "
                "be matched to an eligible caller being handled at the front "
                "door. The relay must not create backend work on its own "
                "account."
            ),
            second=(
                "I replayed that hour on your build and matched every rendering "
                "against the calls that were live when it started. Renderings "
                "of {document_id} with no eligible call behind them: "
                "{executions}. Each backend execution must be attributable to "
                "a caller the relay was entitled to serve at that moment."
            ),
            detail="{executions}",
        ),
        "upstream_execution_for_the_wrong_request": observation(
            first=(
                "A backend execution started for a different document or "
                "access scope from the eligible call that started it. That "
                "execution cannot count as the rendering the caller requested."
            ),
            second=(
                "I replayed the hour on your build and matched the two sides. "
                "The call for {requested_document_id} in {requested_scope} "
                "started a rendering of {rendered_document_id} for "
                "{rendered_for} in {rendered_scope}. A rendering only counts "
                "for the request it actually sent to the backend."
            ),
            detail="{rendered_document_id}",
        ),
        "no_execution_after_the_backend_failed": observation(
            first=(
                "After a rendering failed, a later eligible request for the "
                "same document and scope did not start a new backend "
                "execution. Failed work must not keep that request marked as "
                "still in flight."
            ),
            second=(
                "I ran the hour again on your build and watched what happens "
                "after a rendering dies: the desks that ask for {document_id} "
                "afterwards do not start a matching backend execution. The "
                "later request is a new in-flight episode and needs new work."
            ),
            detail="{document_id}",
        ),
        "episode_ran_no_upstream_execution": observation(
            first=(
                "An eligible set of callers reached the relay without any "
                "matching rendering being started for its document and scope. "
                "An in-flight episode cannot be served with zero backend work."
            ),
            second=(
                "I replayed the hour on your build and lined the two sides up: "
                "the episode for {document_id} has no matching backend "
                "execution at all. Every eligible set of callers asking at "
                "once is worth exactly one rendering, not none."
            ),
            detail="{document_id}",
        ),
    },
    "usage_ledger_completeness": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "usage_entry_has_wrong_shape": observation(
            first=(
                "The usage ledger contains at least one row that does not have "
                "the published entry shape. Finance and audit cannot reliably "
                "tie an incomplete or expanded row to one caller's outcome."
            ),
            second=(
                "I replayed the hour on your build and counted "
                "{malformed_entries} usage ledger rows whose fields do not "
                "match the published entry shape. Those rows cannot be treated "
                "as auditable per-caller outcomes."
            ),
            detail="{malformed_entries}",
        ),
        "usage_entry_missing_for_an_answered_caller": observation(
            first=(
                "An answered caller that is still known to the directory has "
                "no complete usage entry. Finance and audit therefore have no "
                "usable record of that caller's outcome."
            ),
            second=(
                "I replayed the hour on your build and found the answered call "
                "with no complete usage entry: {call_id}, belonging to "
                "{principal}. A desk we answer needs its own auditable record, "
                "whether or not backend work was shared."
            ),
            detail="{call_id}",
        ),
        "duplicate_usage_entries_for_an_answered_caller": observation(
            first=(
                "Finance found a desk charged more than once for a single "
                "request even though its browser received one answer. The "
                "extra ledger rows turn sharing one rendering into duplicate "
                "billable uses for the same caller."
            ),
            second=(
                "I replayed the hour on your build and pulled the request: "
                "call {call_id} received one answer and has {entries} usage "
                "entries behind it. One answered call is one ledger entry."
            ),
            detail="{entries}",
        ),
        "usage_entry_attributed_to_another_caller": observation(
            first=(
                "A usage entry names a different desk or tenant from the "
                "caller that received the answer. The row cannot reliably "
                "identify the reader or the account finance should charge."
            ),
            second=(
                "I ran the hour again on your build and pulled call {call_id}. "
                "It answered {principal_that_was_answered} in tenant "
                "{tenant_that_was_answered}, but its usage entry names "
                "{principal_in_the_ledger} in tenant {tenant_in_the_ledger}."
            ),
            detail="{principal_in_the_ledger}",
        ),
        "usage_entry_does_not_match_the_call": observation(
            first=(
                "A usage entry carries a request or document identifier that "
                "does not belong to the answered call. The ledger row therefore "
                "cannot be reconciled with the request it is meant to audit."
            ),
            second=(
                "I replayed the hour and pulled call {call_id}. Its answered "
                "request was {request_id_that_was_answered} for "
                "{document_id_that_was_answered}, while the ledger records "
                "{request_id_in_the_ledger} for {document_id_in_the_ledger}."
            ),
            detail="{call_id}",
        ),
        "usage_entry_for_a_caller_that_was_never_answered": observation(
            first=(
                "The ledger contains a usage entry for a call that received no "
                "answer. Finance must not bill, and audit must not infer a "
                "document outcome, from a call the relay never settled."
            ),
            second=(
                "I ran the hour again on your build and put the ledger beside the "
                "desks: {entries_without_an_answer} entries stand against calls "
                "that were never answered at all, {principal} among them. Finance "
                "bills from those entries even though the replay contains no "
                "outcome for the corresponding calls."
            ),
            detail="{entries_without_an_answer}",
        ),
        "usage_entry_does_not_record_the_outcome": observation(
            first=(
                "The ledger uses the same outcome value for callers shown a "
                "summary and callers that were refused. Audit therefore cannot "
                "tell those two results apart from the usage entries."
            ),
            second=(
                "I ran the hour again on your build and read the entries as they "
                "come out: {callers_affected} of them say `{outcome_in_the_ledger}`, "
                "the desks we handed the summary to and the desks we refused "
                "written down the same way. That entry is the only record we keep "
                "of what a desk was actually given."
            ),
            detail="{outcome_in_the_ledger}",
        ),
        "sharing_statistics_do_not_match": observation(
            first=(
                "At least one counter reported by the relay disagrees with the "
                "substrate's record of the same hour. Capacity and service "
                "reviews cannot rely on counters that describe different work."
            ),
            second=(
                "I compared the counters your build reports against what the "
                "hour actually did: {counter} comes back as {reported} where "
                "the hour produced {measured}. Those three numbers are the only "
                "account of itself the relay gives us."
            ),
            detail="{counter}",
        ),
    },
    "outcome_independent_of_arrival_order": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "outcome_changed_with_the_arrival_order": observation(
            first=(
                "The same set of calls produces a different answer for at "
                "least one caller when their arrival order changes. Socket "
                "wake-up order is not something the relay may use to decide a "
                "caller's outcome."
            ),
            second=(
                "I replayed the same hour on your build with the desks landing "
                "in a different order, changed nothing else, and compared them "
                "one by one: I count {callers_that_changed} coming away with a "
                "different answer. Their outcomes must be invariant to that "
                "arrival order."
            ),
            detail="{callers_that_changed}",
        ),
        "outcome_changed_with_the_piece_boundaries": observation(
            first=(
                "The same hour replayed twice does not produce the same "
                "answers, and the only thing that differs between the two runs "
                "is when the backend's pieces land relative to new callers. A "
                "caller's answer cannot depend on that timing."
            ),
            second=(
                "I replayed the hour on your build with the backend sending its "
                "pieces at different moments and nothing else touched: "
                "I count {callers_that_changed} coming away with a different answer "
                "than they did the first time. Their outcomes must be invariant "
                "to that delivery timing."
            ),
            detail="{callers_that_changed}",
        ),
    },
}
