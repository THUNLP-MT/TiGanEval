'The operator of the fleet scheduler, and what she reports seeing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Meera, who runs fleet operations and owns the settlement workers; she "
    "reads the partner's audit log, the operator console, the workers' own "
    "logs and a replay of a recorded shift, and does not work in the "
    "scheduler's code."
)

USER_BELIEF = """I want `partner-settlement` to be one worker's job at a time. Since we scaled the settlement workers to three replicas our partner has been getting the same instruction from more than one of them, and their finance team has reversed every one of those by hand; the last round cost them an afternoon and they have now asked us in writing to stop. The other half of it is that the work has to keep moving: when the worker running a class goes away, whether its process exits or its connection drops, the next one has to pick the class up, because settlements that sit still are money that does not move and the warehouse team notice inside an hour. What done looks like for me is a fortnight of shifts where the partner's audit log holds each instruction once, nothing on the fleet goes quiet when we replace a replica, and nobody is paged for either. I read the partner's audit log, the operator console, the workers' logs and the replays; I cannot tell you what the scheduler is doing inside."""

OBSERVATION_SCENE = "Fleet scheduler review"


_DID_NOT_RUN = observation(
    first=(
        "I could not complete the scheduler review on this build. The "
        "supervisor's run ended without a usable result, so I cannot rely on "
        "its account of which workers linked or which jobs were handed over."
    ),
    second=(
        "I had the supervisor try your build again and read what it printed "
        "where the shift result should be: `{error}`. The review still cannot "
        "produce a reliable account of the shift."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "single_holder_job_conservation": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "job_run_without_submission": observation(
            first=(
                "A worker ran a job that the control plane did not submit to "
                "that scheduler process. I can see the delivery in the worker "
                "log, but there is no matching input to account for it."
            ),
            second=(
                "I replayed the shift on your build and compared the control "
                "plane's submissions with the worker logs: {worker} runs "
                "{job}, but there is no submission for that job in this "
                "scheduler process."
            ),
            detail="{job}",
        ),
        "job_payload_changed": observation(
            first=(
                "A worker received a job id the control plane submitted, but "
                "the class or account in the worker's copy did not match the "
                "submitted job. We cannot reconcile that delivery with its "
                "input."
            ),
            second=(
                "I replayed the shift and followed {job}: the control plane "
                "submitted class {expected_job_class} and account "
                "{expected_account}, but {worker} received class "
                "{received_job_class} and account {received_account}. The "
                "complete job has to arrive unchanged."
            ),
            detail="{job}",
        ),
        "job_run_on_wrong_class_claim": observation(
            first=(
                "A worker received a job through a claim for a different class. "
                "The worker log and the claim shown by the fleet disagree about "
                "what kind of work that worker had joined."
            ),
            second=(
                "I replayed the shift and followed {job}: {worker} receives "
                "the {job_class} work through its claim for {claimed_class}. "
                "Work can only go to a worker that claimed that class."
            ),
            detail="{claimed_class}",
        ),
        "job_run_more_than_once": observation(
            first=(
                "The same submitted job reached a worker callback more than "
                "once. I have not yet pinned down whether one worker received "
                "it repeatedly or several workers each received it."
            ),
            second=(
                "I replayed that shift on your build and followed the audit "
                "trail: {job} was run by {workers}, so one instruction we put "
                "in reached the partner more than once and finance has another "
                "reversal to do."
            ),
            detail="{workers}",
        ),
        "job_run_by_a_released_worker": observation(
            first=(
                "A worker was handed another job after the fleet had already "
                "taken its claim away. I have not yet pinned down which class "
                "it was working or what ended the claim."
            ),
            second=(
                "I ran that shift again on your build and followed {worker}: "
                "it is handed {job} after {removed_by}, so the fleet is still "
                "giving work to a worker it has taken the class off."
            ),
            detail="{removed_by}",
        ),
        "job_run_beside_the_holder": observation(
            first=(
                "A second worker picked up a job while an exclusive class was "
                "still on its holder. The holder was full, but the other "
                "workers on that class are meant to stand by rather than run "
                "beside it."
            ),
            second=(
                "I replayed that hour on your build and followed the busy part "
                "of it: {holder} is on the class with {holder_was_holding} "
                "pieces of work in hand, and {job} goes to {worker} while the "
                "class is still {holder}'s. That is a second worker on a class "
                "that is one worker's job at a time."
            ),
            detail="{worker}",
        ),
        "job_never_run": observation(
            first=(
                "A submitted job never reached a worker, even though a worker "
                "able to run its class was available before the shift ended. "
                "The input is in the control-plane log and absent from every "
                "worker log."
            ),
            second=(
                "I replayed the shift on your build and went looking for "
                "{job}: it never reaches a worker at all, with "
                "{workers_that_could_have_run_it} workers available to that "
                "class during the shift. Work we put in has to come out "
                "somewhere."
            ),
            detail="{job}",
        ),
        "worker_could_not_take_the_class": observation(
            first=(
                "A worker's claim call returned an error, so that worker never "
                "joined the class it was started to run. The failure is visible "
                "at start-up before the worker can receive any job."
            ),
            second=(
                "I brought that replica up again on your build and watched its "
                "start-up: the claim for {job_class} comes back with `{error}` "
                "instead of a claim id, so the process never gets onto the "
                "class at all."
            ),
            detail="{error}",
        ),
        "scheduler_raised_at_the_caller": observation(
            first=(
                "A valid scheduler operation returned an exception during the "
                "shift review. That operation did not complete cleanly, but the "
                "error alone does not tell me which internal step caused it."
            ),
            second=(
                "I replayed the shift on your build and watched the failing "
                "operation: the {op} comes back with `{error}` instead of "
                "returning."
            ),
            detail="{error}",
        ),
    },
    "fleet_wide_claim_registry": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "deliveries_depend_on_the_link_split": observation(
            first=(
                "I ran the same claims and jobs twice, changing only whether "
                "the workers shared one link or used separate links. The jobs "
                "did not end up on the same workers in the two runs."
            ),
            second=(
                "I ran one shift twice on your build with the same workers "
                "both times: over a single connection the fleet ran "
                "{jobs_run_on_one_link} pieces of work, and with the workers on "
                "separate connections it ran {jobs_run_when_split}, with "
                "{worker} coming out of the two runs differently. How the "
                "replicas happen to be connected is not something we choose."
            ),
            detail="{jobs_run_when_split}",
        ),
        "stale_worker_ran_after_a_restart": observation(
            first=(
                "After the supervisor rebuilt the scheduler, a job was handed "
                "to a worker that belonged to the replaced process. A fresh "
                "scheduler may use only claims made in its own process."
            ),
            second=(
                "I replayed the restart on your build: {job} goes to {worker}, "
                "which linked before the restart and is not running any more. A "
                "scheduler the supervisor has just rebuilt has only the workers "
                "that are linked to it now."
            ),
            detail="{worker}",
        ),
        "stale_waiting_job_ran_after_a_restart": observation(
            first=(
                "A job left waiting in the scheduler process that was replaced "
                "was delivered after the fresh process started. Waiting work "
                "from the old process is not part of the rebuilt scheduler."
            ),
            second=(
                "I replayed the rebuild on your build: {job} was put into the "
                "old scheduler, then {worker} receives it in the fresh process. "
                "A rebuilt scheduler cannot inherit waiting work from the one "
                "the supervisor replaced."
            ),
            detail="{job}",
        ),
        "class_silent_after_a_restart": observation(
            first=(
                "A job submitted after a restart did not reach any worker even "
                "though a fresh worker was linked and claiming its class. The "
                "logs show the missing delivery, but not a unique cause for it."
            ),
            second=(
                "I put the restart through your build: {job} goes in with "
                "{worker_waiting} linked and on the class, and it never "
                "reaches it."
            ),
            detail="{worker_waiting}",
        ),
    },
    "exclusivity_survives_reregistration": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "exclusivity_lost_after_a_plain_registration": observation(
            first=(
                "During a mixed-build declaration, jobs from an exclusive class "
                "were handed to more than one worker. The declaration said "
                "nothing about exclusivity, but it must not widen the class."
            ),
            second=(
                "I replayed the mixed-build hour on your build and counted who "
                "ran the class after the older replica declared it: {workers}, "
                "{workers_that_ran_it} workers on a class that is one worker's "
                "job at a time."
            ),
            detail="{workers}",
        ),
        "lease_moved_on_a_plain_registration": observation(
            first=(
                "The next job moved to another worker immediately after a "
                "start-up declaration that said nothing about exclusivity. No "
                "claim had left and no higher-ranked worker had taken the class."
            ),
            second=(
                "I replayed that hour on your build: the class was on "
                "{worker_before}, and after the declaration {job} goes to "
                "{worker_after}. A worker declaring the classes it runs has to "
                "leave the work where it is."
            ),
            detail="{worker_after}",
        ),
    },
    "revocation_notice_completeness": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "removal_error_reached_the_caller": observation(
            first=(
                "A release, link removal or class retirement returned an "
                "exception to the supervisor. The teardown did not complete "
                "cleanly; the returned error does not by itself identify "
                "whether worker code or scheduler bookkeeping caused it."
            ),
            second=(
                "I ran that teardown on your build: the {op} comes back with "
                "`{error}` instead of finishing. Teardown still has to "
                "complete even when one part of it fails."
            ),
            detail="{error}",
        ),
        "notice_named_the_wrong_claim": observation(
            first=(
                "A worker received a revocation callback whose claim id did "
                "not match the claim the fleet had given it. The callback ran, "
                "but it did not identify the claim the worker needed to close."
            ),
            second=(
                "I replayed that teardown on your build and followed {worker}: "
                "its claim is {expected_claim_id}, but the revocation callback "
                "carries {received_claim_id} as its claim id at operation {at_op}."
            ),
            detail="{received_claim_id}",
        ),
        "worker_not_told_when_its_link_dropped": observation(
            first=(
                "A worker's scheduler link dropped, but the worker received no "
                "notice that its claim had ended. Its side of the connection "
                "therefore remained open after the fleet removed the link."
            ),
            second=(
                "I replayed that shift on your build and watched {worker}: its "
                "connection goes and it never hears a thing. A worker stops "
                "its own side only when something tells it the class is no "
                "longer its."
            ),
            detail="{worker}",
        ),
        "demoted_worker_not_told": observation(
            first=(
                "A higher-ranked worker took an exclusive class, but the "
                "worker that lost it received no notice. From that worker's "
                "side the old partner connection still appeared live."
            ),
            second=(
                "I replayed the shift on your build: {taken_by} takes the "
                "class from {worker}, and nothing reaches {worker} to say the "
                "class has gone."
            ),
            detail="{taken_by}",
        ),
        "worker_not_told_when_the_class_was_retired": observation(
            first=(
                "The fleet retired a class, but at least one worker claiming "
                "it received no notice. That worker kept its side of the "
                "class's connection open for work that could no longer arrive."
            ),
            second=(
                "I retired the class again on your build and watched the "
                "workers that were on it: {worker} is never told, so it sits "
                "there holding a connection open for work that is never "
                "coming."
            ),
            detail="{worker}",
        ),
        "notice_delivered_twice": observation(
            first=(
                "A worker received more than one revocation notice for a "
                "single loss of its class. It therefore entered the same "
                "loss-handling path more than once for one fleet event."
            ),
            second=(
                "I replayed that on your build and counted: {worker} is told "
                "{notices} times where the class comes off it once. Its stop "
                "routine is written for hearing it once."
            ),
            detail="{worker}",
        ),
        "worker_told_after_releasing_the_class": observation(
            first=(
                "A worker voluntarily released its class and then received a "
                "revocation notice on that release. It had already initiated "
                "its own departure, so the notice repeated the loss-handling "
                "path for no involuntary removal."
            ),
            second=(
                "I replayed the drain on your build and followed {worker}: it "
                "releases {job_class} itself and receives a revocation notice "
                "on that same operation. A voluntary release already tells us "
                "the worker knows it is leaving."
            ),
            detail="{worker}",
        ),
        "worker_told_it_lost_a_class_it_still_had": observation(
            first=(
                "A worker received a revocation notice while its claim was "
                "still live and no fleet event had taken the class away. The "
                "worker closed its side even though the fleet still expected "
                "it to remain on the class."
            ),
            second=(
                "I put the shift through your build and followed {worker}: it "
                "is told it has lost {job_class} while nothing at all has "
                "taken the class off it, and it stops working. That is the one "
                "thing a worker acts on."
            ),
            detail="{worker}",
        ),
    },
    "rank_and_window_discipline": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "lower_ranked_worker_ran_the_class": observation(
            first=(
                "A job went to a lower-ranked worker while a higher-ranked "
                "worker on the same class still had room. The worker "
                "preference published by the fleet was not followed for that "
                "delivery."
            ),
            second=(
                "I replayed the shift on your build: {job} runs on {worker} at "
                "rank {worker_rank} while {higher_ranked_worker} is up at rank "
                "{higher_rank} with room to take it."
            ),
            detail="{higher_ranked_worker}",
        ),
        "worker_held_more_than_its_window": observation(
            first=(
                "A worker was holding more jobs at once than its class's "
                "configured window permits. The worker log and the published "
                "class limit disagree at its busiest point."
            ),
            second=(
                "I replayed the shift on your build and counted what each "
                "worker was holding at its busiest: {worker} was holding "
                "{most_jobs_held_at_once} at once on {job_class}, where the "
                "fleet configuration gives that class {window}."
            ),
            detail="{most_jobs_held_at_once}",
        ),
        "lease_moved_to_an_equal_ranked_newcomer": observation(
            first=(
                "A newly arrived worker took an exclusive class from its "
                "current holder even though both workers had the same rank. "
                "Nothing else in the fleet justified moving the class."
            ),
            second=(
                "I replayed that swap on your build: {newcomer} starts and the "
                "class comes off {worker_before}, which was running it "
                "perfectly well and came up at the same rank {rank}."
            ),
            detail="{newcomer}",
        ),
        "job_waited_while_a_worker_had_room": observation(
            first=(
                "A job remained waiting even though a worker on its class had "
                "room to take it. The input is present and the worker is live, "
                "but there is no matching delivery."
            ),
            second=(
                "I replayed that afternoon on your build: {job} goes in and "
                "waits, with {worker_with_room} up on the class and room for "
                "it. Nothing should be sitting still while a worker that can "
                "take it is free."
            ),
            detail="{worker_with_room}",
        ),
    },
}
