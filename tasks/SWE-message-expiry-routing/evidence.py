'Owner persona, belief, and Observation contexts for SWE-message-expiry-routing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ravi, on-call for the notification pool. He reads the queue dashboard, the "
    "operator console and the tickets support forwards him; he does not read "
    "the broker's code."
)

USER_BELIEF = (
    "I want a stretch of nights where the notification queues do not page "
    "anyone. Last night one bad notification held the whole worker pool and "
    "four hours of customer alerts went out late, and while the downstream "
    "service was slow the feed queue climbed until I was clearing it by hand. "
    "Support forwards me the 'where did my notification go' tickets and right "
    "now I answer them by guessing. Done, for me, is a month of deploys and "
    "feed trouble in which the queues keep moving, customers stop getting "
    "alerts they should never have received, and I can answer a support ticket "
    "from the console instead of from memory."
)

OBSERVATION_SCENE = "On-call's queue review after a night of notification traffic"


DID_NOT_RUN = observation(
    first=(
        "I ran the overnight traffic through your build before this morning's queue "
        "review, but it did not leave a complete usable operation history. I can "
        "only judge the part before the first break in that history, so I cannot "
        "sign off what the queues did afterwards."
    ),
    second=(
        "I ran the traffic again and found the first break in this run's usable "
        "timeline. The console reports it as: {error}. Until the review has a "
        "complete history, I cannot rely on conclusions drawn from the operations "
        "that follow that point."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "accounted_message_disposition": {
        "candidate_execution_failed": DID_NOT_RUN,
        "broker_operation_failed": observation(
            first=(
                "During the overnight review, a broker operation raised instead of "
                "completing. The console cannot give me a reliable account of the "
                "state produced by that step or of work that depends on it."
            ),
            second=(
                "I put the same traffic through again and followed the operation "
                "timeline. At `{label}` the broker raises instead of completing, "
                "so I cannot treat the state after that operation as a completed "
                "broker result."
            ),
            detail="{label}",
        ),
        "settlement_record_wrong": observation(
            first=(
                "Support compared the broker operations with the settlement history "
                "and found a history change that the operation did not justify. The "
                "notification may have moved, but the console is not a reliable "
                "account of how it left."
            ),
            second=(
                "I replayed the same traffic and compared the history after each "
                "operation. At `{label}` it first stops matching the copy and "
                "operation responsible for the change, so support cannot use that "
                "history to explain the notification."
            ),
            detail="{label}",
        ),
        "message_unaccounted": observation(
            first=(
                "The queue review found a notification copy that is no longer in its "
                "queue and has no settlement line for leaving it. Support has no "
                "broker record from which to explain where that copy went."
            ),
            second=(
                "I went looking for that shape in last night's traffic with your "
                "channel in place. The copy of `{message_id}` that went into "
                "`{queue}` is not there any more and there is no line in the "
                "console for it leaving. A notification that leaves a queue for "
                "any reason has to leave a line support can read."
            ),
            detail="{message_id}",
        ),
        "dead_lettered_copy_never_arrived": observation(
            first=(
                "The console says a notification copy moved to a dead-letter queue, "
                "but the end of the review has no copy or later settlement line for "
                "it there. On-call cannot find the copy the console says was set "
                "aside."
            ),
            second=(
                "I followed the copies the console says were moved, starting with "
                "`{message_id}` from `{queue}`. Its source line is present, but the "
                "final queue and settlement views contain no corresponding copy in "
                "the configured destination."
            ),
            detail="{message_id}",
        ),
        "message_settled_more_than_once": observation(
            first=(
                "Support pulled the history of one notification and found it "
                "recorded more than once as having left the same queue. The console "
                "therefore counts one departure multiple times and cannot support "
                "reliable totals."
            ),
            second=(
                "I checked last night's traffic for it after your change. The "
                "console holds {entries} separate lines for `{message_id}` leaving "
                "one queue, so the morning totals count it more than once. One "
                "copy leaving a queue is one line."
            ),
            detail="{message_id}",
        ),
        "message_settled_and_resident": observation(
            first=(
                "The console records a notification copy as finished with a queue "
                "while the dashboard still shows that same copy under the queue. "
                "Support cannot tell whether it is finished or still available to "
                "a worker."
            ),
            second=(
                "I went back through the same traffic looking for that shape. It "
                "is still there: the console has `{message_id}` finished with "
                "`{queue}` and the broker is still holding a copy of it in there. "
                "A finished notification must not be somewhere a worker can take "
                "it."
            ),
            detail="{message_id}",
        ),
        "message_resident_twice": observation(
            first=(
                "The dashboard counts the same notification copy more than once "
                "under one queue name. The worker pool cannot treat both entries as "
                "independent work without risking duplicate handling."
            ),
            second=(
                "I watched the dashboard through the overnight traffic again: it "
                "counts {places} representations of `{message_id}` under one queue "
                "name. One accepted notification copy should occupy one broker "
                "place at a time."
            ),
            detail="{message_id}",
        ),
        "dead_letter_provenance_missing": observation(
            first=(
                "On-call followed a notification copy that had already moved and "
                "found that its movement history is missing or inconsistent. The "
                "console cannot reliably say which queue it left or what caused "
                "the move."
            ),
            second=(
                "I followed the movement records again and inspected "
                "`{message_id}`. It {missing}, so on-call cannot reconstruct that "
                "copy's route from the broker's own history."
            ),
            detail="{message_id}",
        ),
        "dead_letter_payload_altered": observation(
            first=(
                "The content shown for a notification copy in the broker no longer "
                "matches the content supplied when it was published. A worker or "
                "replay cannot safely use a copy whose payload changed in transit."
            ),
            second=(
                "I published one through your broker myself and followed it through "
                "the console. The copy of `{message_id}` associated with `{queue}` "
                "is not carrying what we published. A notification is only useful "
                "if its content survives every place the broker puts it."
            ),
            detail="{message_id}",
        ),
    },
    "bounded_redelivery": {
        "candidate_execution_failed": DID_NOT_RUN,
        "poison_message_retained": observation(
            first=(
                "The retry drill ended with a notification still first in the "
                "worker queue. The review therefore cannot show that the queue "
                "drains after the retry sequence finishes."
            ),
            second=(
                "After your change I started the poison-message drill and looked "
                "at the queue when it stopped: `{message_id}` is still first in "
                "line in `work`, so the next worker request would encounter a copy "
                "the drill should already have finished with."
            ),
            detail="{message_id}",
        ),
        "redelivery_bound_exceeded": observation(
            first=(
                "The operation history shows one notification copy handed out from "
                "the same queue more times than that queue allows. A failing copy "
                "can therefore continue occupying workers after its allowance is "
                "used."
            ),
            second=(
                "I counted the handouts through last night's traffic. One copy, "
                "`{message_id}`, came out of the same queue {handouts} times, past "
                "what that queue allows. After the last attempt it has to go "
                "somewhere other than back to the workers."
            ),
            detail="{message_id}",
        ),
        "discarded_message_redelivered": observation(
            first=(
                "A worker looked at a notification, decided it was not ours to "
                "send, and threw it away. The next worker that asked for work was "
                "handed the same one. What a worker decides about a notification "
                "does not stick."
            ),
            second=(
                "I took the poison-message drill as far as `take-6`, the handout "
                "right after the worker throws one away. It comes back holding the "
                "notification that was just discarded. A discarded copy must never "
                "come out of that queue again."
            ),
            detail="take-6",
        ),
        "requeue_order_wrong": observation(
            first=(
                "A worker handed a failed notification back for another attempt, "
                "but the next worker was given a different notification while that "
                "one stayed in line. The retry sequence no longer matches the queue "
                "behaviour the operators rehearse."
            ),
            second=(
                "I followed the same handback one operation at a time. At "
                "`{label}` the worker was not given the notification the previous "
                "worker had just returned for another attempt."
            ),
            detail="{label}",
        ),
        "redelivery_count_off_by_one": observation(
            first=(
                "A delivery carried a retry number one higher than the handouts that "
                "actually preceded it in that queue. Worker decisions based on that "
                "number would use the wrong attempt."
            ),
            second=(
                "I read the number on each handout as the operator took work out. "
                "At `{label}` the delivery came with {reported}, one more than the "
                "times that copy had been handed out of that queue before. The "
                "number is the handouts that came before this one, so the first "
                "handout is zero."
            ),
            detail="{label}",
        ),
        "redelivery_count_not_reset": observation(
            first=(
                "The first handout of a notification from a dead-letter queue "
                "reported a nonzero retry count even though that copy had not been "
                "handed out from this queue before. The worker is being given a "
                "count that does not describe this queue."
            ),
            second=(
                "I went through `{message_id}` by hand where it arrives in "
                "`{queue}`. Its first handout there reports {reported}, although no "
                "handout of that copy from this queue came before it."
            ),
            detail="{message_id}",
        ),
        "redelivery_count_wrong": observation(
            first=(
                "The retry number on a delivery does not match the earlier handouts "
                "of that copy from its current queue. The worker pool cannot use "
                "that number to decide where it is in the retry sequence."
            ),
            second=(
                "I went through last night's handouts one at a time. At `{label}` "
                "the delivery came with {reported}, which is not the number of "
                "times that copy had already come out of that queue. Every "
                "delivery carries the count for that copy in the queue it is in."
            ),
            detail="{label}",
        ),
    },
    "publication_time_expiry": {
        "candidate_execution_failed": DID_NOT_RUN,
        "expired_message_delivered": observation(
            first=(
                "A worker was handed a notification copy when the console clock was "
                "already at or past the deadline stored on it. That exposes stale "
                "work to the delivery pool."
            ),
            second=(
                "I sat with the operator and watched the handouts as the clock "
                "moved on. One copy went to a worker with the console reading "
                "{handed_out_at}, and the deadline on it was {expires_at}. Nothing "
                "past its deadline reaches a worker, whatever else is waiting "
                "behind it."
            ),
            detail="{expires_at}",
        ),
        "queue_ttl_not_applied": observation(
            first=(
                "A notification published without its own lifetime was stored with "
                "a deadline that does not reflect the lifetime declared by its "
                "queue. The operator cannot tell from that copy when it becomes "
                "stale."
            ),
            second=(
                "I published one alert to both queues the way the fan-out does it "
                "and compared the two copies. The one waiting in `{queue}` is not "
                "carrying the deadline implied by that queue's declared "
                "{queue_message_ttl}-second lifetime."
            ),
            detail="{queue}",
        ),
        "message_ttl_not_applied": observation(
            first=(
                "A notification published with its own shorter lifetime was stored "
                "with a different deadline. The delivery pool cannot rely on that "
                "copy becoming stale at the time the publisher requested."
            ),
            second=(
                "I replayed the expiry sweep and looked at `pub-short`, the "
                "publish that carries its own five-second life. The copy that was "
                "stored does not carry the deadline implied by that request."
            ),
            detail="pub-short",
        ),
        "publisher_lifetime_shortened": observation(
            first=(
                "A digest notification published with its own longer lifetime was "
                "stored with a deadline that does not match the publisher's "
                "request. Finance cannot rely on the stored deadline representing "
                "the lifetime it asked for."
            ),
            second=(
                "I published the summary again through your build and looked at "
                "what got stored. At `pub-nightly` the publish asks for "
                "{published_with_ttl} seconds, but the stored copy does not carry "
                "the corresponding deadline."
            ),
            detail="pub-nightly",
        ),
        "expired_copy_left_waiting_after_handout": observation(
            first=(
                "After a worker handout completed, a notification already at or "
                "past its deadline was still waiting in the same queue. The stale "
                "copy remains available to affect a later handout."
            ),
            second=(
                "I stepped through last night's traffic to the handout at "
                "`{label}`. Once it was done, a copy past its deadline was still "
                "waiting in `{queue}`, where a later worker request can encounter "
                "it."
            ),
            detail="{label}",
        ),
        "expired_message_retained": observation(
            first=(
                "When the overnight review ended, the dashboard still showed a "
                "notification waiting whose deadline was not later than the "
                "console clock. Stale traffic remains mixed with work that is "
                "actually pending."
            ),
            second=(
                "I let last night's traffic run to the end. With the console "
                "clock reading {clock} there is still a copy waiting in `{queue}` "
                "whose deadline was {expires_at}. When the operator stops, nothing "
                "past its deadline is still sitting ready anywhere."
            ),
            detail="{clock}",
        ),
        "drain_expired_count_wrong": observation(
            first=(
                "The expiry sweep printed a count different from the number of "
                "copies already at or past their deadlines when it started. The "
                "operator cannot use that count as a report of what the sweep "
                "removed."
            ),
            second=(
                "I ran the sweep at `{label}` again and counted what was actually "
                "past its deadline in that queue when it started: "
                "{past_their_deadline}. The number the sweep printed is not that, "
                "so the operator cannot use it to decide whether to run it again."
            ),
            detail="{past_their_deadline}",
        ),
    },
    "bounded_queue_overflow": {
        "candidate_execution_failed": DID_NOT_RUN,
        "queue_length_bound_exceeded": observation(
            first=(
                "During the overnight traffic, a capped queue held more waiting "
                "notifications than its declared limit. The dashboard no longer "
                "reflects the bound operators use to judge the backlog."
            ),
            second=(
                "I watched the queues through last night's traffic. `{queue}` "
                "was holding {waiting} at one point where its `max_length` is "
                "{max_length}. A queue is not allowed to hold more than that at "
                "any point, whatever put the notifications there."
            ),
            detail="{waiting}",
        ),
        "unacked_message_evicted": observation(
            first=(
                "A notification copy that a worker was already holding disappeared "
                "from the broker during another operation. The worker can no longer "
                "finish that delivery against the state it received."
            ),
            second=(
                "I looked at the same stretch again with the console open: by "
                "`{label}` the copy of `{message_id}` a worker was already holding "
                "had disappeared from the broker. What a worker is holding is not "
                "waiting in the queue and the queue's limit must not touch it."
            ),
            detail="{message_id}",
        ),
        "overflow_evicted_wrong_message": observation(
            first=(
                "At the end of the overflow burst, the notifications left in the "
                "feed queue do not match the result of shedding the copies that had "
                "waited longest. On-call cannot rely on the remaining backlog being "
                "the fresher work."
            ),
            second=(
                "I took the overflow burst through and looked at what was left in "
                "`feed` at the end: {still_waiting_ids}. Shedding the ones that "
                "had waited longest would have left {should_still_be_waiting}."
            ),
            detail="{should_still_be_waiting}",
        ),
        "overflow_kept_an_older_copy": observation(
            first=(
                "While enforcing a queue limit, the broker removed a notification "
                "that entered the queue later and kept one that had already waited "
                "there longer. It shed the fresher copy instead of the older "
                "backlog."
            ),
            second=(
                "I compared the queue entries at `{label}`. In `{queue}` the broker "
                "removed `{message_id}`, which entered at {waiting_since}, while "
                "`{kept}`, which entered at {kept_since}, remained waiting."
            ),
            detail="{message_id}",
        ),
        "overflow_victim_not_dead_lettered": observation(
            first=(
                "The accepted publishes and final feed backlog identify a copy that "
                "should have a limit-departure line, but the settlement history has "
                "no such line for it. On-call cannot account for that copy."
            ),
            second=(
                "I ran the overflow burst and compared the accepted publishes, final "
                "backlog and console history. There is no line saying "
                "`{message_id}` left `feed` because the queue was full."
            ),
            detail="{message_id}",
        ),
        "unrelated_queue_disturbed": observation(
            first=(
                "After the feed burst, a separate queue with no limit did not hold "
                "the one notification published to it. Two teams share this broker, "
                "and one queue's traffic is changing the other queue's visible "
                "state."
            ),
            second=(
                "I watched `side` through the overflow burst, the queue with no "
                "limit on it that the burst publishes one alert to and never "
                "touches again. At the end it is holding {waiting}. A queue's "
                "limit is its own business."
            ),
            detail="side",
        ),
    },
    "restart_durable_broker_state": {
        "candidate_execution_failed": DID_NOT_RUN,
        "post_restart_delivery_failed": observation(
            first=(
                "After a deploy, a worker request returned no notification even "
                "though the dashboard immediately before it showed live work "
                "waiting in that queue. The queue is not usable for the work that "
                "survived the restart."
            ),
            second=(
                "I did the same thing here: took the drill up to the deploy, "
                "brought it back, and asked for work. At `{label}` the queue "
                "handed out nothing. A deploy has to leave the queue usable."
            ),
            detail="{label}",
        ),
        "restart_lost_settlement_record": observation(
            first=(
                "Support opened a notification's history after a deploy and lines "
                "that were present immediately beforehand had changed or "
                "disappeared. No queue operation between those two views explains "
                "the change."
            ),
            second=(
                "I compared the console immediately around `{label}`. The settlement "
                "history is different after that deploy even though no queue "
                "operation happened between the two pictures."
            ),
            detail="{label}",
        ),
        "restart_lost_resident_message": observation(
            first=(
                "A notification copy the broker held immediately before a deploy "
                "was absent immediately afterwards. The restart lost work that had "
                "not left the broker."
            ),
            second=(
                "I took the drill through a deploy and compared the two pictures. "
                "The broker held `{message_id}` under `{queue}` before the deploy, "
                "and that copy is not present afterwards."
            ),
            detail="{message_id}",
        ),
        "acknowledged_message_resurrected": observation(
            first=(
                "A notification recorded as acknowledged before a deploy appeared "
                "in a queue again afterwards. It is available for duplicate "
                "handling even though the console already says it finished."
            ),
            second=(
                "I took the deploy drill through and followed `{message_id}`, one "
                "a worker acknowledges before the deploy. It is back in `{queue}` "
                "afterwards, waiting to be sent a second time. Once a notification "
                "is acknowledged it is finished for good."
            ),
            detail="{message_id}",
        ),
        "restart_lost_dead_letters": observation(
            first=(
                "At least one notification present in a dead-letter queue before a "
                "deploy was missing from that queue afterwards. On-call has lost "
                "failed work that was waiting for review."
            ),
            second=(
                "I compared `orders.dead` immediately around the deploy. A copy "
                "present there beforehand is absent afterwards, without an "
                "operation that removed it."
            ),
            detail="orders.dead",
        ),
        "restart_lost_redelivery_state": observation(
            first=(
                "A notification rejected before a deploy was returned to the same "
                "queue by the rejection that reached its delivery allowance after "
                "the deploy. The copy remains available after the operation that "
                "should have finished its attempts in that queue."
            ),
            second=(
                "I followed `{message_id}` in `{queue}` across the deploy. It had "
                "{rejections_before_the_deploy} rejection events before the deploy, "
                "and at `{label}` the rejection that reaches the queue's allowance "
                "puts it back into that queue."
            ),
            detail="{message_id}",
        ),
    },
}
