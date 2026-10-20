'Owner persona, belief, and Observation contexts for SWE-recovery-construct-effects.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Rosa, the billing engineer who owns the pricing-rule language. She reads the "
    "ledger finance reconciles, the morning triage board, the rating vendor's "
    "invoice and what a replay of a recorded night prints; she does not read the "
    "code that runs a recovery region."
)

USER_BELIEF = (
    "I want a month of rating runs where a rule that cannot price one order costs "
    "us that order and nothing else. On 14 July `bundle_discount` blew up on two "
    "orders filed with two lines, both came out of the run at nothing with charges "
    "sitting against them, and finance held the whole invoice run until the desk "
    "repriced the pair by hand at 09:15. What I can see is what a run leaves "
    "behind: the ledger rows finance reconciles, the morning triage board "
    "operations groups the night's incidents on, the rating vendor's invoice, and "
    "what a replay of a recorded night prints. Finance and the vendor both read "
    "those and both come to me about them. Done, for me, is a month in which no "
    "customer is billed for work the run threw away, the vendor's line stops "
    "growing, and neither finance nor operations brings me a night again."
)

OBSERVATION_SCENE = "The billing engineer's morning read of the rating run's ledger and board"


DID_NOT_RUN = observation(
    first=(
        "I put your build on the rating box before this morning's billing review. "
        "One of the rating runs stopped part way instead of reaching the end, so "
        "its ledger and incident summary are incomplete. I cannot use that run to "
        "judge the change."
    ),
    second=(
        "I isolated that run and tried it once more. It stopped part way again. "
        "Where the completed result should be, the console holds one line: {error}. "
        "Until that run gets from its first order to its last I cannot judge the "
        "change."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "single_branch_effects": {
        "candidate_execution_failed": DID_NOT_RUN,
        "duplicate_charges_for_one_order": observation(
            first=(
                "A customer rang the billing desk this morning about one order being "
                "billed more than once. It is one order, priced by one rule, on one "
                "night, and the invoice has it on there twice. Finance has stopped "
                "the run of invoices while I work out how far it goes."
            ),
            second=(
                "I pulled the ledger rows for that order on your build. Order {order} "
                "has {charges} charge lines against it from {rule}, adding up to "
                "{amount}, and the run only ever settled on one price for it. "
                "Whichever way the rule got there, the customer is charged once."
            ),
            detail="{charges}",
        ),
        "priced_order_left_no_ledger_rows": observation(
            first=(
                "Finance opened the month's reconciliation and there is next to "
                "nothing in the ledger to reconcile against. The invoice run has "
                "prices for the orders and the ledger has no rows behind them, so "
                "nobody can say what any of those prices is made of. They have "
                "stopped the month until somebody can."
            ),
            second=(
                "I read the night back on your build. Order {order} came out of "
                "{rule} priced at {value} and there is not one row in the ledger "
                "against it. Whichever branch reaches a price, its work is what "
                "finance reconciles the price against."
            ),
            detail="{value}",
        ),
        "effects_kept_for_an_unpriced_order": observation(
            first=(
                "The reconciliation is out again, and this time it is orders with no "
                "price on them at all. The invoice run has nothing to send for those "
                "orders, and the ledger has work sitting against them. Finance is "
                "asking me which of the two is wrong."
            ),
            second=(
                "I read the night back on your build. Order {order} came out of "
                "{rule} with no price, and the ledger still carries rows against it "
                "— {charges} of them, worth {amount}. An order the run gave up on "
                "has to leave the ledger where it found it."
            ),
            detail="{amount}",
        ),
        "order_priced_at_wrong_value": observation(
            first=(
                "A depot has disputed an invoice because the price on our copy does "
                "not agree with the rule and order they priced. The ledger is there "
                "and only one branch survived, but the number handed to invoicing is "
                "not the number that branch produces. Finance has held the invoice."
            ),
            second=(
                "I priced that order again on your build. Order {order} came out of "
                "{rule} as {outcome} at {value}; the same order through that rule's "
                "winning branch comes to {expected_value}. The number handed back "
                "has to be the number from the branch whose ledger rows we kept."
            ),
            detail="{value}",
        ),
        "ledger_rows_do_not_match_winning_branch": observation(
            first=(
                "Finance can price an order, but the ledger rows under it do not "
                "match the work produced by the branch that priced it. The total and "
                "the audit trail no longer explain the invoice, so reconciliation "
                "cannot tell which work actually stands."
            ),
            second=(
                "I read order {order} back on your build. It came out of {rule} as "
                "{outcome}, with {observed_rows} kept rows marked {observed_branch}; "
                "the branch that produced this result has {expected_rows} rows marked "
                "{expected_branch}. When those counts and marks agree, the row amounts "
                "or audit notes differ. The surviving ledger has to be that branch's "
                "own work."
            ),
            detail="{observed_branch}",
        ),
    },
    "signal_transparency": {
        "candidate_execution_failed": DID_NOT_RUN,
        "budget_abort_absorbed": observation(
            first=(
                "The reason we have a limit on how long one order may be worked on is "
                "that a rule once walked every lane of an order until morning and "
                "nobody could tell which rule was doing it. On your build the run got "
                "past that order with a price on it and said nothing, so the rule is "
                "still in there and I have no way of finding it."
            ),
            second=(
                "I ran the same night again and watched order {order}. {rule} used "
                "{steps} of the {step_budget} steps that order is allowed and the run "
                "still handed it a price of {value}. When the run stops a rule that "
                "will not stop on its own, that has to come out of the night, not "
                "turn into a number on an invoice."
            ),
            detail="{steps}",
        ),
        "budget_abort_filed_as_a_rule_fault": observation(
            first=(
                "Operations opened a rules incident on us off last night's summary, "
                "and a couple of us went through that rule before we worked out there "
                "was nothing in it to find. The run had stopped working on the order "
                "itself, because the order had had its share of the night. The "
                "morning went on the wrong thing and the rule that will not stop is "
                "still in there."
            ),
            second=(
                "I ran that night again on your build and watched the order the run "
                "gives up on. Order {order} used {steps} of the {step_budget} steps "
                "{rule} is allowed on one order, and then came off the night as "
                "{outcome}, as though the rule had raised something. The run stopping "
                "a rule is the run's own doing and has to reach the summary as that."
            ),
            detail="{steps}",
        ),
        "halt_ignored": observation(
            first=(
                "The desk pulled the halt switch at 03:40 because the prices coming "
                "out looked wrong, and the run carried on to the end of the night "
                "anyway. Invoices went out on a night we had already decided not to "
                "trust. That switch is the only way anybody has of stopping this "
                "thing once it is running."
            ),
            second=(
                "I halted a night on your build myself, on order {order}. The run "
                "priced that order regardless and went on to price {orders_after} "
                "more after it. Nothing the desk does stops a run that will not let "
                "the halt through."
            ),
            detail="{orders_after}",
        ),
    },
    "lease_conservation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "leases_open_at_the_end": observation(
            first=(
                "The rating vendor invoiced us for reservations held all day and asked "
                "whether we meant to. We did not: the night finished hours before, and "
                "they were still holding capacity for us. It also means the next "
                "night's weighed orders queue behind reservations nobody is using."
            ),
            second=(
                "I counted what your build still had open after the night had finished: "
                "{open_leases}, the first of them {reference}, taken by {rule}. Whatever "
                "a rule takes out with the vendor has to go back before we are done with "
                "that order, whichever way that order ended."
            ),
            detail="{open_leases}",
        ),
        "two_reservations_held_at_once": observation(
            first=(
                "The vendor refused one of our reservations at renewal this week and "
                "the weighed orders on that night went unpriced. Their answer was that "
                "we were asking to hold capacity twice over for the same order, which "
                "their contract does not let us do."
            ),
            second=(
                "I counted them on your build. Order {order} had {held_at_once} "
                "reservations open at the same moment under {rule}, where our contract "
                "allows {max_open_leases}. One order holds one at a time, and anything "
                "we have finished with goes back before the next one is taken."
            ),
            detail="{held_at_once}",
        ),
        "cleanup_failure_swallowed": observation(
            first=(
                "Finance found an order on the invoice that the ledger had already "
                "been closed for. The close failed and the run priced it anyway, so a "
                "customer has an invoice line for a night we are not allowed to bill "
                "them for and finance has to reverse it by hand."
            ),
            second=(
                "I traced that order through your build. Order {order} came out of "
                "{rule} priced at {value}, and the close that runs after it did not go "
                "through. When the close fails, that is the answer for the order; the "
                "price the rule had reached does not survive it."
            ),
            detail="{value}",
        ),
        "close_never_ran_for_that_order": observation(
            first=(
                "Finance closed the month and the close report came up short. An "
                "order that went through one of the closing rules has no close "
                "against it at all, so the ledger behind that order was never "
                "closed and finance has reopened the month to write it by hand. "
                "Operations had the same order on the board as a rules incident, "
                "and two of us spent a morning on a rule that had done nothing "
                "wrong."
            ),
            second=(
                "I read that order back on your build. Order {order} came off "
                "{rule} filed as {label}, and the night booked no settlement slot "
                "for it at all, so the close never ran. The close runs for every "
                "order that rule takes on, and an order that comes off with no "
                "price is the one finance needs it for."
            ),
            detail="{label}",
        ),
        "close_count_wrong_for_order": observation(
            first=(
                "The month-end close report does not agree with the orders that went "
                "through a closing rule. One order's settlement count is not one, so "
                "finance cannot close the ledger without checking that order by hand."
            ),
            second=(
                "I traced order {order} under {rule} on your build. It ended as "
                "{outcome}, and its settlement slot was booked {opens} times and "
                "returned {closes} times. The closing branch runs once however the "
                "region ends, and the one slot it books is returned before the order "
                "leaves."
            ),
            detail="{closes}",
        ),
    },
    "attempt_budget": {
        "candidate_execution_failed": DID_NOT_RUN,
        "attempts_over_budget": observation(
            first=(
                "The rating vendor's invoice went up again this month and finance has "
                "asked me to explain it. We are paying for evaluated attempts, and the "
                "number of attempts on the invoice is running well ahead of the number "
                "of orders we priced. The cap we agreed with them is the whole reason "
                "the number is in the rulebook."
            ),
            second=(
                "I counted the attempts on your build, order by order. Order {order} "
                "was evaluated {attempts} times under {rule}, where the rulebook "
                "allows {max_attempts}. That cap is what finance signed with the "
                "vendor; it is per order and it is not per rule."
            ),
            detail="{attempts}",
        ),
        "retries_spent_without_falling_back": observation(
            first=(
                "The rating vendor was down for two hours last night and the quoted "
                "orders came through to the morning with nothing on them. Those rules "
                "carry a flat price for exactly that case — it is what we agreed with "
                "the depots the first time the vendor's line went — and not one of the "
                "orders got it. Depots were ringing about missing invoices before "
                "eight."
            ),
            second=(
                "I put a night of refused quotes through your build. Order {order} "
                "took {attempts} of the {max_attempts} evaluations the rulebook allows "
                "it under {rule}, and then came off the night as {outcome} with no "
                "price on it at all. When the tries a rule is allowed are spent, the "
                "price that rule carries for the trouble is what is left to use."
            ),
            detail="{attempts}",
        ),
        "retried_order_left_unpriced": observation(
            first=(
                "The vendor's line went for a minute last night and came straight "
                "back, and the depot orders that were being quoted in that minute "
                "still came through to the morning with nothing on them. Those are "
                "the rules we flagged to have another go for exactly that, and the "
                "rate was there the moment they asked again."
            ),
            second=(
                "I put that minute through your build. Order {order} was evaluated "
                "{attempts} of the {max_attempts} times the rulebook allows it under "
                "{rule} and came off the night as {outcome} with no price on it, "
                "while the vendor answered the ask that followed. A rule we flagged "
                "has another go while the order has one to spend, whatever came out "
                "of it the first time."
            ),
            detail="{attempts}",
        ),
        "retried_order_priced_by_its_branch": observation(
            first=(
                "Finance queried a run of depot invoices that came in at the flat "
                "rate on a night the vendor was answering. The depots have the "
                "vendor's rate for those orders on their own copy and ours say "
                "something else, so every one of them is being disputed."
            ),
            second=(
                "I traced them on your build. Order {order} was evaluated {attempts} "
                "times under {rule}, the last of those reached a price, and the order "
                "still came off the night as {outcome} at {value} from the rule's own "
                "branch. The evaluation that reaches a price is the one the order is "
                "billed from; the flat rate is for when none of them does."
            ),
            detail="{value}",
        ),
        "exhaustion_answered_with_a_price": observation(
            first=(
                "One of the estimate rules put a flat price on an order the vendor had "
                "refused all night, and it went out on an invoice. Nobody looked at "
                "it, because as far as the night was concerned that order priced. An "
                "order we have already spent everything on is exactly the one somebody "
                "has to see before a depot is billed for it."
            ),
            second=(
                "I traced that order on your build. Order {order} had used {attempts} "
                "of the {max_attempts} evaluations it is allowed before {rule} reached "
                "that branch, and the branch priced it at {value} anyway. An order "
                "with nothing left comes off the night as one, not as a price."
            ),
            detail="{value}",
        ),
        "exhaustion_reported_as_inner_fault": observation(
            first=(
                "Operations routed a whole night of unpriced orders to me as a rules "
                "problem, and the rules were fine — the vendor was down. They read the "
                "board, the board said the rules had thrown something, and three "
                "people spent the morning on the wrong thing."
            ),
            second=(
                "I looked at what your build filed for those orders. Order {order} "
                "used {attempts} of its {max_attempts} evaluations under {rule} and "
                "then went on the board under {label}, the last thing the rule said. "
                "Running out of evaluations is its own answer and is filed as one; "
                "operations takes that row to the vendor, not to us."
            ),
            detail="{attempts}",
        ),
    },
    "label_invariance": {
        "candidate_execution_failed": DID_NOT_RUN,
        "label_follows_message_text": observation(
            first=(
                "The morning board has the same trouble sitting in two rows again. "
                "Operations sized it from the smaller row, gave it to one person for "
                "an afternoon, and it came back the next night at the size the two "
                "rows added up to. They have asked me why the board splits it."
            ),
            second=(
                "I compared two of them on your build. Order {order} and order "
                "{sibling} met the same trouble under {rule}, and yours filed one as "
                "{label} and the other as {sibling_label}. The wording of the two "
                "differs because the engine puts the order's own numbers in it; what "
                "went wrong is the same thing."
            ),
            detail="{sibling_label}",
        ),
        "clause_missed_sibling_fault": observation(
            first=(
                "Two orders on the same night hit the same trouble under the same "
                "rule, and only one of them came out with a price. The other went "
                "through to the morning unpriced, and the depot it belongs to was "
                "still asking about it at eleven."
            ),
            second=(
                "I put both through your build. Order {order} came off {rule} as "
                "{outcome} while order {sibling} went through the same trouble under "
                "the same rule and came out priced. A rule written to cover that "
                "trouble covers it for both of them; the length of an order does not "
                "come into it."
            ),
            detail="{sibling}",
        ),
        "guard_did_not_take_its_own_label": observation(
            first=(
                "The depots are chasing orders that came through the night with "
                "nothing on them. Each of those orders met exactly the trouble the "
                "rule pricing it keeps a branch for — those branches are the rebates "
                "we agreed with them for those cases — and not one of the orders got "
                "the branch's price. They are doing them by hand and asking me when "
                "it stops."
            ),
            second=(
                "I put those orders through your build. Order {order} came off {rule} "
                "with no price at all, and the trouble it met is the one that rule "
                "keeps its branch for, the branch written for {guard}. A branch "
                "written for a kind of trouble has to take that kind when it comes."
            ),
            detail="{guard}",
        ),
        "guard_took_an_unnamed_label": observation(
            first=(
                "One of the weighed rules has been quietly pricing orders it was never "
                "written to price. It carries a branch for one kind of trouble and it "
                "is being used for trouble of another kind entirely, so orders that "
                "should have come to us as incidents are going out on invoices at the "
                "branch's flat price."
            ),
            second=(
                "I checked which ones on your build. Order {order} met {label} trouble "
                "under {rule}, whose branch is written for {guard}, and the branch "
                "priced it anyway. A branch written for one kind of trouble takes that "
                "kind and leaves the rest to come out."
            ),
            detail="{order}",
        ),
        "fault_filed_under_wrong_label": observation(
            first=(
                "The morning board has an incident in the wrong published row. The "
                "orders in that row do not have the kind of trouble the heading says, "
                "so operations sent the incident to the wrong team and lost the "
                "morning before they found it."
            ),
            second=(
                "I checked the incident your build wrote for order {order}. Under "
                "{rule} it raised {fault_class} and was filed as {label}, while the "
                "board's class mapping files that class as {expected_label}. The "
                "published class mapping, not a locally consistent substitute, owns "
                "the row."
            ),
            detail="{label}",
        ),
    },
}
