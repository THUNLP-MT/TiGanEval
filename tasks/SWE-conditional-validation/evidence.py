'Owner persona, belief, and Observation contexts for SWE-conditional-validation.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Maya, the backend engineer who owns the order platform's entity documents; "
    "she reads support tickets, the dashboard the agents work from, the partner "
    "importer's rejection report and the review queue, not the write path's code."
)

USER_BELIEF = """Support closed thirty-eight tickets this week where an order is sitting in shipped with no tracking number. The customer's tracking page is blank, the courier hand-off never happens, and the agent has to go and find the parcel by hand. Every one of those tickets comes back to the same thing: somebody once wrote a pair check for the payment fields in orders/retiring_guards.py and nobody ever wrote one for shipping. The half-finished check in orders/policy.py looks like where those rows got through.

What I want is for the entity document to be the one place a pair is written down. I put a rule into orders/entities/order.json, the platform holds everyone to it, and I get to delete the hand-written file instead of being the person who remembers which pairs exist. The people this hurts are the support agents closing the same ticket every week and the customers who cannot see where their parcel is.

Done, for me, is a week with no tracking tickets in it, nothing turned away at checkout that our own documents are happy with, and nobody's morning ruined by a rule that was written down and never held anyone to anything."""

OBSERVATION_SCENE = "Morning triage on the order platform"


_REPLAY_STOPPED = observation(
    first=(
        "The nightly replay of the write path stopped part way through, so there is nothing to "
        "go through this morning and nobody can say what the platform did with the writes that "
        "never came back with a verdict."
    ),
    second=(
        "I put the same traffic through your build myself and it stops in the same place. The "
        "write log holds one line where the rest of the run should be: {error}"
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "admission_matches_reference": {
        "candidate_execution_failed": _REPLAY_STOPPED,
        "write_path_operation_failed": observation(
            first=(
                "One record in the filing queue came back as an error instead of a decision. "
                "The team cannot tell whether the platform took it, so they have held that "
                "record for somebody to inspect."
            ),
            second=(
                "Ran the same hour of traffic on your build: {payload} has no acceptance "
                "decision, and the write log says: {error}"
            ),
            detail="{error}",
        ),
        "payload_wrongly_refused": observation(
            first=(
                "The filing team has a record waiting that the platform turned away even "
                "though its document is satisfied. They cannot continue that record until "
                "somebody explains the refusal."
            ),
            second=(
                "Went through the hour of traffic on your build and read the refusals: {payload} "
                "comes back turned away — {refusal} — and everything its document asks of it is "
                "on it."
            ),
            detail="{payload}",
        ),
        "payload_wrongly_accepted": observation(
            first=(
                "A record reached the table without an attribute its document requires. "
                "Support found the incomplete record before the write path reported a problem."
            ),
            second=(
                "Went through the hour of traffic on your build: {payload} went through with "
                "no {missing} on it, and the document it is written against does not allow that."
            ),
            detail="{missing}",
        ),
        "admitted_item_wrong": observation(
            first=(
                "The write path said it had taken a record, but the next service received a "
                "different item. The acceptance decision was green while the item handed "
                "on did not match the document's processed input."
            ),
            second=(
                "Put the same traffic through your build and followed the accepted item: "
                "{payload} is taken, but its result first differs at {attribute}."
            ),
            detail="{attribute}",
        ),
    },
    "update_guarded_by_the_store": {
        "candidate_execution_failed": _REPLAY_STOPPED,
        "update_path_operation_failed": observation(
            first=(
                "One write in the job came back as an error instead of a commit or refusal. "
                "The job has no safe decision for that record and has left it for review."
            ),
            second=(
                "Put the job's queue through your build: {update} has no update result, and "
                "the write log says: {error}"
            ),
            detail="{error}",
        ),
        "violating_update_committed": observation(
            first=(
                "A job moved a record into a value that requires a companion attribute, and "
                "the companion is still absent after the committed write. A downstream service "
                "now has an incomplete record to process."
            ),
            second=(
                "Watched the job run against your build: {update} on {key} went straight "
                "through, and afterwards that record has {controller} moved on with no "
                "{attribute} on it."
            ),
            detail="{attribute}",
        ),
        "dependent_removal_committed": observation(
            first=(
                "A write cleared an attribute from a record whose controlling value still "
                "requires it. The platform reported the write committed and left an incomplete "
                "record behind."
            ),
            second=(
                "Reproduced it on your build with {update}: {key} still has {controller} where "
                "it was, {attribute} has gone, and the write went through."
            ),
            detail="{key}",
        ),
        "caller_condition_dropped": observation(
            first=(
                "A job wrote over a record it had asked the platform not to touch. It sends "
                "its own precondition with the write precisely so that it loses that race "
                "rather than winning it, and it won."
            ),
            second=(
                "Ran that write again on your build: {update} committed against {key} although "
                "the precondition it sent, {condition}, does not hold for what is stored."
            ),
            detail="{key}",
        ),
        "harmless_update_refused": observation(
            first=(
                "A write that does not leave any pair it touches incomplete came back refused. "
                "That record is still waiting even though this change is safe to apply."
            ),
            second=(
                "Put one of the stuck jobs through your build: {update} on {key} came back "
                "refused — {refusal} — although nothing this change touches is left short."
            ),
            detail="{key}",
        ),
        "update_result_wrong": observation(
            first=(
                "The store reported a successful update, but the resulting row does not match "
                "the requested transition. The job moved on using a success result that was "
                "not true of what was stored."
            ),
            second=(
                "Read the row back after {update} on your build: {key} was reported committed, "
                "but the stored result first differs at {attribute}."
            ),
            detail="{attribute}",
        ),
    },
    "stored_items_stay_reachable": {
        "candidate_execution_failed": _REPLAY_STOPPED,
        "read_path_operation_failed": observation(
            first=(
                "A stored record fails when support tries to read it through the dashboard. "
                "The agent cannot inspect that record and has had to leave its ticket open."
            ),
            second=(
                "Read the same older record on your build and it returns no usable view. "
                "The dashboard reports: {error}"
            ),
            detail="{error}",
        ),
        "stored_item_not_returned": observation(
            first=(
                "An agent opened a record and a value held in the table was missing or changed "
                "on the screen. The stored record and the support view no longer agree."
            ),
            second=(
                "Read that record through your build and put it beside what the table holds: "
                "{attribute} is stored against {key} and does not come back."
            ),
            detail="{attribute}",
        ),
        "projected_read_failed": observation(
            first=(
                "A dashboard list asked for a restricted set of fields and did not receive the "
                "corresponding row. That list entry is missing or incomplete for support."
            ),
            second=(
                "Opened the same list on your build: the view for {projection} does not match "
                "the stored projection, and the dashboard reports: {error}"
            ),
            detail="{projection}",
        ),
        "legacy_item_update_refused": observation(
            first=(
                "The support tool refused a safe correction to an older record. That record "
                "remains uncorrected even though the change does not worsen its existing pair."
            ),
            second=(
                "Tried one of the corrections on your build: the write to {key} came back "
                "refused — {refusal} — and it was not touching the pair that record is short of."
            ),
            detail="{key}",
        ),
        "legacy_item_update_wrong": observation(
            first=(
                "The support tool said it had saved a correction to an older record, but the "
                "resulting table row does not match that correction. The success message does "
                "not describe what was stored."
            ),
            second=(
                "Read {key} back after {update} on your build: the save was reported successful, "
                "but {attribute} is not the correction the agent made."
            ),
            detail="{attribute}",
        ),
    },
    "contract_agrees_with_the_writer": {
        "candidate_execution_failed": _REPLAY_STOPPED,
        "contract_operation_failed": observation(
            first=(
                "The nightly hand-off lacks a complete decision for one published document or "
                "one of the records checked against it. The partner cannot safely rely on that "
                "part of the hand-off."
            ),
            second=(
                "Ran the hand-off on your build: {label} does not complete its contract and "
                "writer comparison, and the log says: {error}"
            ),
            detail="{error}",
        ),
        "contract_accepts_what_the_writer_refuses": observation(
            first=(
                "The partner has been importing records their side that our own write path "
                "would never take, and they come back to us as exceptions two days later. Their "
                "form lets somebody through and then our API says no to the same record."
            ),
            second=(
                "Ran the same items through the document your build publishes: {payload} "
                "passes it, while our own write path turns it away — {refusal}"
            ),
            detail="{refusal}",
        ),
        "contract_refuses_what_the_writer_accepts": observation(
            first=(
                "The partner's importer is rejecting records we took happily an hour earlier "
                "and their desk is opening a ticket for each one. They are reading the document "
                "we publish, so I cannot tell them they are holding it wrong."
            ),
            second=(
                "Validated the same items against what your build publishes: {payload} comes "
                "back rejected — {complaint} — out of a document that is meant to say what we say."
            ),
            detail="{complaint}",
        ),
        "rebuilt_schema_behaves_differently": observation(
            first=(
                "A schema carried to the reconciliation worker does not behave the same after "
                "the worker rebuilds it. The hand-off changed a decision even though the entity "
                "document did not change."
            ),
            second=(
                "Sent the document across on your build and checked {payload}: its {surface} "
                "changes from {before} to {after} after rebuilding."
            ),
            detail="{payload}",
        ),
    },
    "declarations_are_enforceable": {
        "candidate_execution_failed": _REPLAY_STOPPED,
        "review_operation_failed": observation(
            first=(
                "A proposed document came back from review with a technical error instead of "
                "an approval or refusal. That document cannot move out of the queue yet."
            ),
            second=(
                "Put the queue through your build: {draft} comes back with this where the "
                "verdict should be: {error}"
            ),
            detail="{error}",
        ),
        "physical_name_collision_accepted": observation(
            first=(
                "A document went live with two fields pointing at the same place in the table. "
                "One write can now overwrite a different field without the services knowing."
            ),
            second=(
                "Put the review queue through your build: {draft} was accepted even though "
                "two attributes point at the same stored location."
            ),
            detail="{draft}",
        ),
        "key_count_declaration_accepted": observation(
            first=(
                "A document the store cannot key was approved for publication. The review "
                "said yes even though the document does not identify exactly one record key."
            ),
            second=(
                "Put the review queue through your build: {draft} was accepted with "
                "{key_count} key attributes in it."
            ),
            detail="{key_count}",
        ),
        "unenforceable_declaration_accepted": observation(
            first=(
                "A document went live with a conditional pair the platform cannot enforce. "
                "The document promises a constraint that the write path cannot reliably hold."
            ),
            second=(
                "Went through the queue on your build: the pair on {attribute} names "
                "{controller} — {why} — and the document still went through."
            ),
            detail="{controller}",
        ),
        "enforceable_declaration_refused": observation(
            first=(
                "A document the platform can enforce came back refused this morning. The valid "
                "change it carries is still sitting in the review queue."
            ),
            second=(
                "Put the queue through your build myself: {draft} comes back refused — {error} "
                "— and there is nothing wrong with it."
            ),
            detail="{draft}",
        ),
    },
}
