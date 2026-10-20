'Owner persona, belief, and Observation contexts for SWE-durability-acknowledgement.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dennis Aluko, the storage engineer who owns the write path of the key-value "
    "store. He goes by the node console, the report a restarted node prints while "
    "it recovers, and what the replication team brings him in the morning."
)

USER_BELIEF = (
    "I want to stop losing writes we have already acknowledged. At 03:14 on "
    "Tuesday node c-7 restarted and writes the replicas had been told were "
    "safe were not in the log when it came back; we rebuilt the replica set, "
    "were down 26 minutes, and I have been in front of the incident review ever "
    "since. The ack path used to sleep 200ms after a commit and hope the log had "
    "caught up; I took the sleep out and put a prototype behind it that answers "
    "from the sequence number the write path has just applied, so what we tell a "
    "client is still a guess in both directions: sometimes ahead of what the "
    "device has taken, sometimes sitting on a write it took long ago. I treat "
    "the feed callback and wait_for_durability as two views of the same "
    "acknowledgement, so if their released sequence numbers agree with recovery "
    "I expect both sides to be telling the same story. Done, for me, is a quarter "
    "in which nothing we acknowledged is "
    "missing after a recovery, the replication team stops asking whether the "
    "numbers on my side can be trusted, and I can stop defending the write path "
    "in that review."
)

OBSERVATION_SCENE = "The write path review after a night of commit traffic on the storage nodes"


DID_NOT_RUN = observation(
    first=(
        "The drill box did not return a usable session console for this build. "
        "Without a completed result I cannot compare the durable number with the "
        "log, account for the events, or take the change to the write path review."
    ),
    second=(
        "I ran the drill again and it still did not return a usable session. The "
        "one line available from this attempt is: {error}. Until a plain run goes "
        "end to end I cannot judge anything else about the change."
    ),
    detail="{error}",
)


CALL_FAILED = observation(
    first=(
        "One of the calls the commit pipeline made into the write path failed during "
        "the drill. The console marks that step as failed, so rows recorded after it "
        "cannot turn this into one complete, trustworthy run."
    ),
    second=(
        "I put it on the drill box again and found the first failed step. At "
        "`{label}` the console recorded: {error}. That pipeline call has to complete "
        "before the rest of the session can be trusted."
    ),
    detail="{error}",
)


OUTPUT_INCOMPLETE = observation(
    first=(
        "The drill box did not return the complete, trustworthy session console it "
        "was asked for. Without every requested step from the shared engine I cannot "
        "tell what the log held, which clients were released, or how the close ended."
    ),
    second=(
        "I ran the drill again and found the first unusable part of the result. At "
        "`{label}` it reports: {error}. I need the whole requested session before "
        "any of its durability claims can be used."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "durable_watermark_matches_log": {
        "candidate_execution_failed": DID_NOT_RUN,
        "session_output_incomplete": OUTPUT_INCOMPLETE,
        "tracker_call_failed": CALL_FAILED,
        "watermark_ahead_of_the_log": observation(
            first=(
                "At one point in the node-console run, the number the write path "
                "published as durable was higher than the number recovery could get "
                "from the log. The ack path could answer a client from that unsupported "
                "number if the node stopped there."
            ),
            second=(
                "I put the same traffic through on your build and read the two "
                "numbers side by side. At `{label}` the write path said {reported} "
                "where the log had reached {reference}. That number is the whole "
                "promise: it has to be the log's, not the memtable's."
            ),
            detail="{label}",
        ),
        "watermark_went_backwards": observation(
            first=(
                "The node console shows the published durable number falling between "
                "two steps in the same run. Once a consumer has acted on that number, "
                "the write path has no way to retract the acknowledgement."
            ),
            second=(
                "I watched the number through the whole run. At `{label}` it came "
                "back as {reported} after having been {previous}. Whatever else it "
                "does it only ever goes up."
            ),
            detail="{label}",
        ),
        "watermark_behind_the_log": observation(
            first=(
                "At one point in the node-console run, recovery could read farther "
                "into the log than the durable number the write path published. A "
                "client waiting on that number can be held after its write is already "
                "on the device."
            ),
            second=(
                "I ran last night's traffic again and stopped at `{label}`: the log "
                "holds up to {reference} and the write path was still reporting "
                "{reported}. A commit that rode along inside somebody else's fsync "
                "is as durable as the one that asked for it."
            ),
            detail="{label}",
        ),
    },
    "release_never_precedes_the_log": {
        "candidate_execution_failed": DID_NOT_RUN,
        "session_output_incomplete": OUTPUT_INCOMPLETE,
        "tracker_call_failed": CALL_FAILED,
        "event_released_an_unlogged_write": observation(
            first=(
                "The node console records the replication feed receiving a successful "
                "durability event for a sequence number recovery could not read from "
                "the log at that same step. A stop there would leave the feed having "
                "acknowledged a write the device did not hold."
            ),
            second=(
                "I stepped through the traffic on your build to find the moment it "
                "happens. At `{label}` the feed was told sequence number {seq} was "
                "safe while the log held only up to {log_holds_up_to}. Nothing goes "
                "out to the feed before the device has taken those bytes."
            ),
            detail="{seq}",
        ),
        "waiter_released_an_unlogged_write": observation(
            first=(
                "The node console records a parked client being released successfully "
                "while recovery still could not read that sequence number from the "
                "log. If the node stopped at that point, the client would have success "
                "for a write the device did not hold."
            ),
            second=(
                "I parked a client on a number and watched what let it go. At "
                "`{label}` the client waiting on sequence number {seq} was released "
                "with the log holding only up to {log_holds_up_to}. A client is "
                "released by the device, not by the memtable."
            ),
            detail="{seq}",
        ),
    },
    "one_event_per_sync_commit": {
        "candidate_execution_failed": DID_NOT_RUN,
        "session_output_incomplete": OUTPUT_INCOMPLETE,
        "tracker_call_failed": CALL_FAILED,
        "durability_event_claimed_a_lost_write": observation(
            first=(
                "The device controller refused a write during the drill, but the "
                "replication feed received a successful durability event for a commit "
                "stranded behind that refusal. The feed can act on that event even "
                "though recovery cannot return the commit."
            ),
            second=(
                "I ran the drill again on your build and followed "
                "`{correlation_id}`. The feed got its event for sequence number "
                "{seq} carrying nothing to say the device had refused the write. A "
                "commit that will never be durable has to say so where the feed can "
                "see it."
            ),
            detail="{seq}",
        ),
        "durability_event_carried_a_false_error": observation(
            first=(
                "The replication feed received a durability event carrying an error "
                "for a commit recovery can read from the log. A client that trusts "
                "that event can retry a write the device already holds."
            ),
            second=(
                "I put last night's traffic through your build and read the events "
                "off the wire. `{correlation_id}`, sequence number {seq}, was covered "
                "by the fsync at `{label}` and reached the feed carrying "
                "`{reported}`. The device took that write. An event says something "
                "went wrong only when something went wrong."
            ),
            detail="{seq}",
        ),
        "durability_event_carried_wrong_error": observation(
            first=(
                "The device controller refused a write, but the replication feed "
                "received a different error for that commit. The feed therefore does "
                "not carry the storage failure that actually stopped the write."
            ),
            second=(
                "I followed sequence number {seq}, `{correlation_id}`, through the "
                "drill. Its event carried `{reported}` where the controller had "
                "reported `{expected}`. The feed needs the refusal that actually "
                "stopped the write."
            ),
            detail="{seq}",
        ),
        "durability_event_missing_for_a_landed_write": observation(
            first=(
                "The event stream is missing a sync-requesting commit that recovery "
                "can read from the log. The device took the write, but the replication "
                "feed received no durability event with which to finish it."
            ),
            second=(
                "I put the events the feed received next to the commits that asked "
                "for an fsync. `{correlation_id}`, sequence number {seq}, was taken "
                "by the fsync at `{label}` and no event ever arrived for it."
            ),
            detail="{seq}",
        ),
        "durability_event_missing_for_a_stranded_write": observation(
            first=(
                "The event stream is missing a sync-requesting commit stranded behind "
                "the device refusal. Recovery cannot return that write, and the feed "
                "received no failure event with which to stop waiting for it."
            ),
            second=(
                "I ran the drill again on your build and put the events the feed "
                "received next to the commits that asked for an fsync. "
                "`{correlation_id}`, sequence number {seq}, was still on the "
                "device's side when the controller reported {first_error}, and "
                "nothing ever went out to say so. Recovery will not find that "
                "write, so the feed is the one thing that can still be told."
            ),
            detail="{seq}",
        ),
        "durability_event_duplicated": observation(
            first=(
                "The replication feed received more than one durability event for the "
                "same sync-requesting commit. A consumer cannot distinguish a repeated "
                "notification from another acknowledgement for that write."
            ),
            second=(
                "I counted the events per commit on your build. Sequence number "
                "{seq}, `{correlation_id}`, arrived {events} times. One commit that "
                "asked for an fsync is one event, whichever fsync ends up covering "
                "it."
            ),
            detail="{seq}",
        ),
        "durability_event_without_a_sync": observation(
            first=(
                "The replication feed received a durability event for a commit that "
                "did not request an fsync. Its presence adds a notification the "
                "commit never asked the engine to produce."
            ),
            second=(
                "I compared what the feed heard with what the commits actually asked "
                "for. Sequence number {seq}, `{correlation_id}`, never asked for an "
                "fsync and the feed was told about it anyway."
            ),
            detail="{seq}",
        ),
        "durability_event_fields_wrong": observation(
            first=(
                "A durability event in the feed does not carry the same commit "
                "metadata as the log record it represents. That leaves the feed with "
                "an acknowledgement it cannot reliably reconcile with the write."
            ),
            second=(
                "I read one event off the wire and put it next to the commit it came "
                "from. For sequence number {seq} the {field} came through as "
                "{reported} where the commit's own is {expected}."
            ),
            detail="{seq}",
        ),
        "durability_event_at_wrong_step": observation(
            first=(
                "The replication feed received a durability event at a different "
                "point from the fsync that decided that commit. The event stream no "
                "longer records when the device produced the corresponding outcome."
            ),
            second=(
                "I followed sequence number {seq}, `{correlation_id}`, step by step. "
                "Its covering fsync was `{expected_label}`, but the event arrived at "
                "`{actual_label}`. The event belongs to the fsync that decided it."
            ),
            detail="{seq}",
        ),
        "durability_event_without_sync_completion": observation(
            first=(
                "The replication feed received a durability event for a "
                "sync-requesting commit even though the session ended without an "
                "fsync reporting an outcome for it. The feed is recording a device "
                "result that never occurred."
            ),
            second=(
                "I followed sequence number {seq}, `{correlation_id}`, through the "
                "session. It requested an fsync, but no fsync ever completed for it; "
                "the feed still received an event at `{actual_label}` carrying "
                "`{reported}`."
            ),
            detail="{seq}",
        ),
    },
    "waiters_settle_exactly_once": {
        "candidate_execution_failed": DID_NOT_RUN,
        "session_output_incomplete": OUTPUT_INCOMPLETE,
        "tracker_call_failed": CALL_FAILED,
        "waiter_left_unresolved_at_close": observation(
            first=(
                "The close drill ended with a client still parked on the node and no "
                "resolution recorded for it. A deploy cannot drain that node while "
                "the write path leaves the client waiting."
            ),
            second=(
                "I took a node through a close on your build with clients still "
                "waiting on it. `{waiter}`, parked on sequence number {seq}, was "
                "never let go. A closing node owes an answer to everyone still "
                "waiting on it, even when the answer is that it is going away."
            ),
            detail="{waiter}",
        ),
        "waiter_left_parked_on_a_landed_write": observation(
            first=(
                "At the last step before close, a client was still parked on a "
                "sequence number recovery could already read from the log. The "
                "connection is being held after the device has answered the write."
            ),
            second=(
                "I followed the parked clients through the run. At `{label}`, the "
                "last step before the node closed, `{waiter}` was still waiting on "
                "sequence number {seq} with the log already holding up to "
                "{log_holds_up_to}. A client whose write is on the device is "
                "released, not left sitting there."
            ),
            detail="{waiter}",
        ),
        "waiter_resolved_more_than_once": observation(
            first=(
                "The node console records more than one resolution for the same "
                "parked client. The connection layer expects one terminal answer and "
                "cannot safely apply another answer to the same handle."
            ),
            second=(
                "I followed one parked client through the run. `{waiter}`, on "
                "sequence number {seq}, was let go {resolutions} times. A client is "
                "released once, whatever happens to the log afterwards."
            ),
            detail="{waiter}",
        ),
        "waiter_blocked_after_the_log_broke": observation(
            first=(
                "After the controller refused a write, the node console still showed "
                "a client parked beyond the last recoverable sequence number. That "
                "write cannot become durable, so continuing to wait only holds the "
                "connection open."
            ),
            second=(
                "I ran the drill again and looked at who was still waiting at the "
                "end. `{waiter}` is parked on sequence number {seq} with the "
                "controller having already reported {first_error}. Nothing after a "
                "refusal will ever become durable, so nobody should still be waiting "
                "for it."
            ),
            detail="{waiter}",
        ),
        "error_not_latched": observation(
            first=(
                "The device refused a write, but a later state read did not retain "
                "that first storage error. The log still has the hole, and the state "
                "no longer reports its cause."
            ),
            second=(
                "I stepped through the same drill on your build. At `{label}` the "
                "state the ack path reads reported `{reported}`, where the controller's "
                "first error was `{expected}`. Every state read after that refusal has "
                "to retain the same error."
            ),
            detail="{reported}",
        ),
        "pending_waiter_count_wrong": observation(
            first=(
                "The pending-waiter number on the node console does not match the "
                "clients whose handles are still unresolved at that step. A drain "
                "check cannot decide whether the node is clear from that count."
            ),
            second=(
                "I compared that number with the clients actually waiting, step by "
                "step. At `{label}` the write path reported {reported} where "
                "{actual} were still parked. The reported number has to match the "
                "clients that are actually still waiting."
            ),
            detail="{label}",
        ),
        "waiter_failed_a_landed_write": observation(
            first=(
                "A parked client was resolved with an error even though recovery can "
                "read its sequence number from the log. That result can make the "
                "caller retry a write the device already holds."
            ),
            second=(
                "I followed `{waiter}`, waiting on sequence number {seq}. The log "
                "had that write, but the client was settled with `{reported}`. A "
                "client gets an error only when its write cannot become durable."
            ),
            detail="{waiter}",
        ),
        "waiter_resolved_without_required_error": observation(
            first=(
                "The close drill resolved a client successfully even though recovery "
                "could not read its sequence number from the log. The node is saying "
                "the write succeeded while closing without it."
            ),
            second=(
                "I followed `{waiter}`, waiting on sequence number {seq}, through "
                "the close. It was released successfully although the log never "
                "reached it. A client whose write cannot land has to receive an "
                "error."
            ),
            detail="{waiter}",
        ),
        "waiter_error_did_not_match_first_failure": observation(
            first=(
                "A client blocked behind a refused write received an error that "
                "does not match the controller's first failure. That result no "
                "longer identifies the storage error that prevented the write from "
                "becoming durable."
            ),
            second=(
                "I followed `{waiter}`, waiting on sequence number {seq}. It was "
                "settled with `{reported}` where the controller first reported "
                "`{expected}`. The first refusal is the reason that write cannot "
                "land."
            ),
            detail="{waiter}",
        ),
    },
    "accounting_independent_of_pipeline_shape": {
        "candidate_execution_failed": DID_NOT_RUN,
        "session_output_incomplete": OUTPUT_INCOMPLETE,
        "tracker_call_failed": CALL_FAILED,
        "wait_stalled_without_a_listener": observation(
            first=(
                "The same parked client was resolved on the primary and left waiting "
                "on a replica that ran without a durability listener. Those replicas "
                "do their own acknowledgement, so the listener cannot be what lets "
                "their clients finish."
            ),
            second=(
                "I put the same traffic through a node with no listener configured "
                "and put it next to the primary. `{waiter}`, parked on sequence "
                "number {seq}, comes back on the primary and never comes back there. "
                "What the engine knows about the device cannot depend on somebody "
                "being attached to hear about it."
            ),
            detail="{waiter}",
        ),
        "state_differed_without_a_listener": observation(
            first=(
                "A primary and a replica reported different durable numbers for the "
                "same commits and device progress; the replica was the run without a "
                "durability listener. That number cannot describe the log if attaching "
                "a listener changes it."
            ),
            second=(
                "I ran one node with a listener attached and one without, and read "
                "the durable number at every step. At `{label}` the one with a "
                "listener said {with_listener} and the one without said "
                "{without_listener}. Same commits, same device, so it is the same "
                "number."
            ),
            detail="{label}",
        ),
        "event_count_lost_without_a_listener": observation(
            first=(
                "The engine reported a different durability-event count for the same "
                "traffic when no listener was attached. That count is meant to record "
                "what the engine produced, so listener registration cannot change it."
            ),
            second=(
                "I ran the same traffic with a listener attached and without one. "
                "The node with a listener counted {with_listener} durability events "
                "and the node without counted {without_listener}. That count is what "
                "the engine produced, not what somebody happened to be there to "
                "hear."
            ),
            detail="{without_listener}",
        ),
        "grouping_changed_what_became_durable": observation(
            first=(
                "The same commit traffic reached a different outcome after only the "
                "pipeline's fsync grouping changed. That grouping is selected by load, "
                "so it cannot decide which writes, clients, or events the engine "
                "finishes."
            ),
            second=(
                "I ran the same commits twice, once with the pipeline batching a few "
                "commits per fsync and once with it batching many, and put the two "
                "runs next to each other: {subject} came out as {when_regrouped} "
                "with the deeper pipeline where the shallower one gave "
                "{when_grouped}. The device took the same bytes both times."
            ),
            detail="{when_regrouped}",
        ),
    },
}
