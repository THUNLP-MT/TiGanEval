'Owner persona, belief, and Observation contexts for SWE-origin-circuit-breaker.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Yusra, on-call for the edge gateway. She reads the gateway's access log, the "
    "upstream teams' dashboards and what a replay of a recorded stretch of "
    "traffic prints; she does not read the call path's code."
)

USER_BELIEF = (
    "I want a stretch of weeks where an upstream going down is that upstream's "
    "problem and not ours. Last Thursday the payments provider timed out, our "
    "request pool filled with calls that were never going to finish, and "
    "checkout was down for eleven minutes; the rest of the fleet went with it, "
    "because everything shares that pool. What I can see is the access log: "
    "which upstream we called, when, what came back, and what we refused to "
    "send. The upstream teams read it too, and they ask me about it. Done, for "
    "me, is a month of upstream trouble in which nobody is paged for something "
    "the gateway did to itself, the services that were fine stay fine, and I "
    "can point at the log and say when we stopped calling a host and when we "
    "started again."
)

OBSERVATION_SCENE = "On-call's review of the gateway access log after a stretch of upstream trouble"


DID_NOT_RUN = observation(
    first=(
        "I put your build on the console box before this morning's gateway review "
        "and started last week's traffic through it. It stopped part way instead "
        "of running to the end, so there is no access log, no call outcomes and "
        "nothing to read. I have nothing to tell the platform team about the "
        "change."
    ),
    second=(
        "I checked the failed run's console output. It stopped before producing "
        "a complete access log, and the last line was: {error}. Until a plain "
        "stretch of traffic runs end to end I cannot judge anything else about "
        "the change."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "shared_origin_isolation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "healthy_origin_refused": observation(
            first=(
                "An upstream that had stayed healthy was refused after a different "
                "origin failed. Its team saw traffic stop at our gateway even "
                "though every request that had reached their side succeeded. Work "
                "that depended on the healthy service stopped with it."
            ),
            second=(
                "I ran the same traffic through your build and read the log by "
                "upstream. The calls to {origin} were the ones we refused, and "
                "nothing at that address had failed all night. What we stop calling "
                "has to be the thing that is failing."
            ),
            detail="{origin}",
        ),
        "failed_origin_still_called": observation(
            first=(
                "The same eleven minutes again. The provider was timing out on "
                "every call, the pool filled with work that was never coming back, "
                "and checkout queued behind it until someone pulled the plug by "
                "hand. That is the incident I opened the ticket about."
            ),
            second=(
                "I went through the log call by call this time. {origin} had turned "
                "down {failures_before} of our calls in a row and `{label}` still "
                "went out to it. After that many in a row we are meant to stop."
            ),
            detail="{failures_before}",
        ),
        "origin_state_split_across_callers": observation(
            first=(
                "The quarterly audit ran overnight and the warehouse host was "
                "unwell for the whole of it. Every call we sent it failed and we "
                "never stopped sending. Warehouse's own on-call asked me why we "
                "were still hammering a host they could see was down."
            ),
            second=(
                "I counted them in the log. {callers} of our service clients sent "
                "those failures between them, {origin} had turned down "
                "{failures_before} calls in a row by the end, and `{label}` still "
                "went out. It is one host; which of our clients noticed first "
                "should not come into it."
            ),
            detail="{callers}",
        ),
        "scheme_origin_collapsed": observation(
            first=(
                "The migration proxy's HTTPS side was failing, and the gateway "
                "stopped its healthy HTTP side too. They use the same address and "
                "port, but they are separate upstream origins and only one of them "
                "was unwell."
            ),
            second=(
                "The failures came through {failing_scheme}, then `{label}` to "
                "{origin} through {healthy_scheme} never left our process. The "
                "scheme is part of which origin we stopped calling."
            ),
            detail="{origin}",
        ),
    },
    "half_open_admission": {
        "candidate_execution_failed": DID_NOT_RUN,
        "probe_flood": observation(
            first=(
                "The pick hub came back at 04:12 and went straight down again. "
                "Every worker that had been waiting on it called it in the same "
                "moment and it fell over under our traffic. That is the second "
                "time this quarter that we have been the thing that finished off "
                "a host on its way back."
            ),
            second=(
                "I counted what left the process at that moment on your build: "
                "{probes_sent} calls to {origin} at once, where that client is set "
                "to {half_open_max}. One of us asks whether a host is back; the "
                "rest wait to be told."
            ),
            detail="{probes_sent}",
        ),
        "retry_took_a_second_slot": observation(
            first=(
                "One logical call was allowed to reach an upstream and was then "
                "refused by our gateway before it could finish. The caller saw a "
                "mid-call failure even though that work had already been admitted."
            ),
            second=(
                "I followed `{label}` through the log. It already had "
                "{attempts_made} attempt rows against {origin} when it ended as a "
                "refusal, with the client set to {half_open_max}. A call we have "
                "already let start has to be allowed to finish."
            ),
            detail="{label}",
        ),
        "retry_released_slot_early": observation(
            first=(
                "While two recovery calls were still in progress against one "
                "upstream, a third waiting call was accepted. One of the first "
                "calls was between retry attempts, not finished."
            ),
            second=(
                "I followed `{label}` in the trace. It was accepted at {origin} "
                "while `{retrying_call}` was between attempts, even though that "
                "client's recovery capacity was {half_open_max}. The first call "
                "had not finished and still owned its place."
            ),
            detail="{label}",
        ),
        "probe_slot_leaked": observation(
            first=(
                "The parcel hub has been unreachable from our side since yesterday "
                "afternoon, and it is not down. Parcel's dashboard shows it healthy "
                "and answering everyone else. Nothing has gone to it from us since "
                "the last time we tried, and nothing is going to."
            ),
            second=(
                "I waited it out and watched the log. {waited_ms} ms after the last "
                "thing we heard from {origin}, `{label}` still did not leave the "
                "process, where the wait for that client is {cooldown_ms} ms. "
                "Nothing on our side has failed since; we have simply stopped."
            ),
            detail="{waited_ms}",
        ),
        "available_probe_slot_refused": observation(
            first=(
                "Search recovery is configured with two lanes, but only one of "
                "the two waiting workers reached it. The other was refused before "
                "it left our process, so recovery ran at half the capacity the "
                "search team had agreed it could take."
            ),
            second=(
                "I replayed that moment. {probes_sent} calls reached {origin}, "
                "although that client is set to {half_open_max}; `{label}` was "
                "the waiting call we refused. Available recovery places are there "
                "to be used."
            ),
            detail="{probes_sent}",
        ),
        "rejected_probe_slot_leaked": observation(
            first=(
                "The feed host answered our first call after the pause to say its "
                "item was not there. The very next request never left our process, "
                "even though that first call had finished and nobody else was "
                "asking whether the host was back."
            ),
            second=(
                "The recovery call to {origin} came back {status}, then `{label}` "
                "was refused. That client has {half_open_max} recovery place and "
                "the finished call was still occupying it."
            ),
            detail="{label}",
        ),
    },
    "blocked_call_inertness": {
        "candidate_execution_failed": DID_NOT_RUN,
        "blocked_call_reached_the_transport": observation(
            first=(
                "We are supposed to have stopped calling notify, and the notify "
                "team can see that we have not. Their host is out and every message "
                "service in the fleet is still pushing calls into it, which is the "
                "whole reason I asked for this."
            ),
            second=(
                "I counted them over the stretch where we should have been leaving "
                "it alone. {sent_in_window} calls still reached {origin}, starting "
                "with `{label}`. If we are not calling a host then nothing goes out "
                "to it at all."
            ),
            detail="{sent_in_window}",
        ),
        "blocked_call_refreshed_the_block": observation(
            first=(
                "Notify has been dark from our side all afternoon. Their host "
                "recovered at about two o'clock and we have not sent it a single "
                "message since we stopped. The queue behind it is four hours deep "
                "now and nothing is draining it."
            ),
            second=(
                "I timed it off the log. {waited_ms} ms after {origin} last actually "
                "failed us, `{label}` still did not go out, where the wait for that "
                "client is {cooldown_ms} ms. Nothing has failed there since we "
                "stopped."
            ),
            detail="{waited_ms}",
        ),
        "unguarded_call_blocked": observation(
            first=(
                "One of the platform calls configured to run unguarded never left "
                "for the mesh host. Health and internal bookkeeping use those "
                "calls because they must keep running while ordinary service "
                "traffic is being refused. The platform work behind that call did "
                "not run."
            ),
            second=(
                "I found it in the log. `{label}` never left the process, although "
                "it is one of the calls that go out unguarded. Those have to keep "
                "running whatever we have decided about the host."
            ),
            detail="{label}",
        ),
        "unguarded_call_counted": observation(
            first=(
                "We stopped calling mesh on the strength of traffic that is not "
                "supposed to have a vote. The internal bookkeeping calls had a bad "
                "run, and then the first real call from a service was turned away, "
                "so a team's sync failed for a reason nothing in their own traffic "
                "explains."
            ),
            second=(
                "I read the run back. {unguarded_failures} of the unguarded "
                "internal calls to {origin} failed first, and then `{label}`, an "
                "ordinary guarded call and the first one, was refused. Calls that "
                "go out unguarded should not be deciding anything."
            ),
            detail="{unguarded_failures}",
        ),
    },
    "logical_call_accounting": {
        "candidate_execution_failed": DID_NOT_RUN,
        "retries_counted_as_failures": observation(
            first=(
                "The batch posting run stopped talking to the ledger after only "
                "two caller-visible postings had failed. The next posting was "
                "refused before it left our process, and the run went out with "
                "nothing posted at all."
            ),
            second=(
                "I put the run through again and counted what the log calls a "
                "posting. `{label}` was refused when only {logical_failures} "
                "postings had actually failed, and the number set for that client "
                "is {threshold}. There are {attempts_so_far} rows in the log for "
                "those postings, because the run tries each one more than once. "
                "One posting is one posting however many times we try it."
            ),
            detail="{logical_failures}",
        ),
        "logical_failures_not_counted": observation(
            first=(
                "The ledger answered nothing but errors for two minutes during last "
                "night's batch and we posted into it the whole time. The postings "
                "queue backed up behind the retries and finance had no ledger to "
                "read this morning."
            ),
            second=(
                "I read the run back. {logical_failures} postings in a row had "
                "failed against {origin} and `{label}` still went out to it, where "
                "the number set for that client is {threshold}."
            ),
            detail="{origin}",
        ),
        "probe_left_before_cooldown": observation(
            first=(
                "We went back to the ledger too early last night. It was still "
                "failing when our first call after the pause went out, so that call "
                "failed too and the pause started over. The batch spent the night "
                "doing that and posted about a third of what it should have."
            ),
            second=(
                "I timed it off the log. `{label}` went out {waited_ms} ms after the "
                "ledger last failed us, where the wait set for that client is "
                "{cooldown_ms} ms. The wait has to run from the last thing that "
                "failed, not from wherever the call began."
            ),
            detail="{waited_ms}",
        ),
    },
    "outcome_classification": {
        "candidate_execution_failed": DID_NOT_RUN,
        "rejection_treated_as_success": observation(
            first=(
                "The catalog host spent yesterday half broken, timing out on some "
                "calls and answering plainly on others, and we never stopped "
                "calling it. Checkout queued behind the timeouts all day and "
                "nothing on our side showed that anything was wrong."
            ),
            second=(
                "I read the answers back in order on your build. {failing_calls} "
                "calls to {origin} came back as the host being unwell and we still "
                "sent `{label}` after them. The ones in between came back {status}, "
                "which is the host telling us an item does not exist. A {status} is "
                "not the host telling us it is well."
            ),
            detail="{failing_calls}",
        ),
        "suppressed_error_not_counted": observation(
            first=(
                "Pricing asked us to hand it error responses rather than raise "
                "them, because it renders its own fallback page. Since then we have "
                "never once stopped calling pricing, however long it is down. Last "
                "night that was forty minutes of the quote page timing out."
            ),
            second=(
                "I put the same traffic through your build. {origin} answered "
                "{status} to three calls in a row and `{label}` went straight out "
                "after them. What one caller wants handed back does not change what "
                "the host said."
            ),
            detail="{origin}",
        ),
        "rejection_counted_as_failure": observation(
            first=(
                "We stopped calling the lookup service this morning and it was "
                "perfectly healthy. It had been asked about four charge ids that do "
                "not exist and it said so, four times. Support could not look "
                "anything up for six minutes."
            ),
            second=(
                "I checked what those four answers actually were: {status} from "
                "{origin} every time, which is the answer to 'is this charge here'. "
                "`{label}` was refused straight after them."
            ),
            detail="{status}",
        ),
        "rejected_probe_closed_the_circuit": observation(
            first=(
                "The feed host was down and we had stopped calling it. The first "
                "call we sent after the pause came back saying the item it asked "
                "for is not there, we read that as the host being well again, and "
                "the traffic went straight back on to a host that was still "
                "failing. The feed team had to bring it up twice inside ten minutes."
            ),
            second=(
                "I traced that moment on your build. The one call we let through, "
                "`{label}`, came back {status}, which is the host saying it has no "
                "such item, and {sent_after_probe} more calls went out to {origin} "
                "after it before we stopped again. It takes {threshold} failures in "
                "a row to put that host out of reach, and that answer was not one "
                "of them."
            ),
            detail="{sent_after_probe}",
        ),
        "transport_error_not_counted": observation(
            first=(
                "Tracking stopped answering us, but the gateway kept sending to "
                "it as if a missing answer were harmless. Those calls sat on the "
                "network boundary until their callers gave up and the dispatch "
                "queue backed up behind them."
            ),
            second=(
                "I replayed it: {origin} gave no answer to {failing_calls} calls, "
                "the threshold is {threshold}, and `{label}` still went out. No "
                "answer is a failure of the origin."
            ),
            detail="{failing_calls}",
        ),
        "transform_error_not_counted": observation(
            first=(
                "The parcel host came back with a body our caller could not read. "
                "We treated that recovery call as harmless and went back during "
                "the new wait, while parcel was still returning broken data."
            ),
            second=(
                "`{label}` reached {origin} only {waited_ms} ms after the unreadable "
                "answer, although that client's wait is {cooldown_ms} ms. A body "
                "the requested transform cannot read is a failed call."
            ),
            detail="{waited_ms}",
        ),
        "successful_probe_left_half_open": observation(
            first=(
                "The pick hub answered the recovery call successfully, but the "
                "gateway still let ordinary work through one call at a time. One "
                "of the next two workers was refused even though the host was back."
            ),
            second=(
                "After the successful recovery answer, only {sent_after_success} "
                "of {expected_calls} ordinary calls reached {origin}; `{label}` "
                "was refused. Success has to return the origin to normal service."
            ),
            detail="{sent_after_success}",
        ),
        "successful_call_did_not_reset_streak": observation(
            first=(
                "Pick recovered successfully, but one later failure immediately "
                "put it out of reach again. The gateway was still carrying the "
                "failures from before recovery instead of starting a new streak."
            ),
            second=(
                "Before the successful recovery answer, {origin} had failed "
                "{failures_before_success} calls at a threshold of {threshold}. "
                "After success and one new failure, `{label}` was refused. A "
                "successful call has to clear the old streak."
            ),
            detail="{label}",
        ),
    },
}
