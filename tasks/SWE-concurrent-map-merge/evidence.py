'The product owner of the whiteboard, and what she reports seeing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Noor, the product owner for the collaborative whiteboard; she reads the "
    "support tickets, replays the sessions support keeps, and looks at two "
    "customers' screens side by side, and does not work in the client's code."
)

USER_BELIEF = """I want a session where two people editing the same card end up looking at the same card. It comes back wrong often enough now that two of our largest accounts have stopped running their planning on it: someone's line goes back to a name they had already replaced, and two people sitting in the same room read different things off the same board. When this is right, the people in a session see one card between them, and when something of theirs really was replaced I can tell them who replaced it instead of guessing. Done for me is a fortnight of planning sessions with neither of those two accounts opening a ticket."""

OBSERVATION_SCENE = "Whiteboard session review with support"


_WOULD_NOT_RUN = observation(
    first=(
        "Support put Thursday's session through the new client build on the "
        "bench and got nothing back at all: no board, no log, nothing on any "
        "of the screens. Two accounts are on the phone about a session they "
        "cannot open."
    ),
    second=(
        "I sat with support and we ran it again on your build. There is no "
        "session in it at all, just `{error}` where the first laptop's board "
        "should be, and nothing behind that even starts, so nobody in the room "
        "gets a card at all."
    ),
    detail="{error}",
)


_STOPPED_MID_SESSION = observation(
    first=(
        "One of the laptops stopped while support was replaying the session. "
        "That copy never produced a complete board and log, so support cannot "
        "tell the person using it that their session finished syncing."
    ),
    second=(
        "I watched it again on your build. `{laptop}` takes {packets_taken} "
        "packets and then comes back with `{error}`, and that copy never takes "
        "anything in again, so whoever is on it is stuck with whatever was on "
        "screen."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "convergent_board_state": {
        "candidate_execution_failed": _WOULD_NOT_RUN,
        "sync_stopped_with_an_error": _STOPPED_MID_SESSION,
        "laptops_show_different_cards": observation(
            first=(
                "Two people came out of the same session looking at different "
                "versions of a card again. They read different things off the "
                "board in the standup, and nobody in the "
                "room could say which was the real one. That is the ticket "
                "these two accounts keep opening."
            ),
            second=(
                "I put the session through again on your build and opened the "
                "same card on both machines: `{laptop}` has {one_value} in "
                "{card_field} on {card_title} and `{other_laptop}` has "
                "{other_value}. Those two were given the same work by the same "
                "people."
            ),
            detail="{other_value}",
        ),
        "redelivery_changed_the_card": observation(
            first=(
                "The service retried a packet it had already delivered and a "
                "board moved under somebody's cursor: a field they had watched "
                "settle changed again with nobody typing. Support cannot "
                "explain to a customer why a card changed when no one touched "
                "it."
            ),
            second=(
                "I ran it again on your build and watched `{laptop}`: "
                "{card_field} on {card_title} read {value_before}, and after "
                "the service resent a packet that copy already had it read "
                "{value_after}. Nobody edited anything in between."
            ),
            detail="{value_after}",
        ),
    },
    "causal_edit_precedence": {
        "candidate_execution_failed": _WOULD_NOT_RUN,
        "sync_stopped_with_an_error": _STOPPED_MID_SESSION,
        "replaced_value_came_back": observation(
            first=(
                "Someone opened a card, read a field, entered the replacement, "
                "and later the card went back to the value they had already "
                "replaced. This report is about which edit survived, not two "
                "laptops showing different cards."
            ),
            second=(
                "I replayed it on your build. {card_field} on {card_title} "
                "reads {value_shown} on `{laptop}`, and "
                "{value_written_on_top} was typed by somebody who had "
                "{value_shown} on their screen while they typed it. The card "
                "is showing the decision that was already overruled; I did not "
                "observe two laptops disagreeing in this incident."
            ),
            detail="{value_written_on_top}",
        ),
        "card_field_shows_no_value": observation(
            first=(
                "A card came back on one laptop with a field simply empty even "
                "though the session contains a value for it and no clear took "
                "that value out. Support cannot rely on that copy's board."
            ),
            second=(
                "I ran the session again on your build: {card_field} on "
                "{card_title} is blank on `{laptop}`, and "
                "{value_that_should_show} is what somebody put there and no "
                "one ever took away."
            ),
            detail="{value_that_should_show}",
        ),
        "card_field_shows_an_unknown_value": observation(
            first=(
                "One of the cards is showing something nobody in the session "
                "typed. The account manager read it out on a call and was "
                "corrected by the customer, which is the worst version of "
                "this that I can think of."
            ),
            second=(
                "I looked again on your build: {card_field} on {card_title} "
                "reads {value_shown} on `{laptop}`, and nobody in that session "
                "ever put that on the field."
            ),
            detail="{value_shown}",
        ),
    },
    "clear_scope_preserves_unseen_edits": {
        "candidate_execution_failed": _WOULD_NOT_RUN,
        "sync_stopped_with_an_error": _STOPPED_MID_SESSION,
        "clear_removed_an_edit_its_author_never_saw": observation(
            first=(
                "A card came back blank in a field two people had been working "
                "on. One of them emptied it on their own screen; the other was "
                "off the network at the time putting a new value into it, and "
                "that unseen value is missing from a replayed copy. Neither "
                "screen contained the other action, so the replay does not put "
                "the edit after the clearing."
            ),
            second=(
                "I ran that session again on your build: {card_field} on "
                "{card_title} is empty on `{laptop}`, and {lost_value} is what "
                "{lost_editor} put there while {clearing_editor} was emptying "
                "it. {clearing_editor} never had that value on screen, and the "
                "replay does not show that edit replacing the clearing."
            ),
            detail="{lost_value}",
        ),
        "cleared_field_still_shows_a_value": observation(
            first=(
                "Somebody emptied a field while looking at its current value, "
                "but a replayed copy still shows that value. The card and the "
                "clear in the session disagree."
            ),
            second=(
                "I checked on your build: {card_field} on {card_title} still "
                "reads {value_still_showing} on `{laptop}` after it was "
                "emptied by somebody who had exactly that value on their "
                "screen when they emptied it."
            ),
            detail="{value_still_showing}",
        ),
    },
    "state_vector_matches_what_it_holds": {
        "candidate_execution_failed": _WOULD_NOT_RUN,
        "sync_stopped_with_an_error": _STOPPED_MID_SESSION,
        "laptop_claims_edits_it_does_not_have": observation(
            first=(
                "In support's packet-by-packet replay, a laptop tells the sync "
                "service it accounts for work that no packet has handed to "
                "that copy. If the service trusts that claim at this boundary, "
                "it will withhold work the laptop still needs."
            ),
            second=(
                "I watched the reconnect on your build. After packet "
                "{packet_number} `{laptop}` is telling the service it accounts "
                "for {claimed_edit} when it has been handed no such thing. "
                "If sync uses that vector at this packet boundary, it will not "
                "offer that missing work."
            ),
            detail="{claimed_edit}",
        ),
        "laptop_asks_for_the_whole_session_again": observation(
            first=(
                "In support's packet-by-packet replay, a laptop's sync summary "
                "leaves out work already held by that copy. If it reconnects "
                "at this boundary, the service will offer that work again."
            ),
            second=(
                "I watched it on your build: `{laptop}` holds {edits_held} of "
                "the session's operations and only admits to "
                "{edits_it_admits_to} of them, so the service sends "
                "a reconnect at this boundary would offer {editor}'s work again."
            ),
            detail="{edits_held}",
        ),
    },
    "merge_account_matches_card": {
        "candidate_execution_failed": _WOULD_NOT_RUN,
        "sync_stopped_with_an_error": _STOPPED_MID_SESSION,
        "operation_missing_from_the_account": observation(
            first=(
                "A customer rang support to ask what had become of a change "
                "she made in Tuesday's session, and the log they answer that "
                "with had nothing about it at all. Support could only tell her "
                "they did not know what the board had done with it, and she has "
                "asked for her team's sessions in writing from now on."
            ),
            second=(
                "I read the log next to the board on your build: on `{laptop}` "
                "it lists {entries_listed} entries for the "
                "{operations_handed} changes that copy was handed, and "
                "{missing_operation} is not one of them. That one is "
                "{editor}'s change to {card_field} on {card_title}, and "
                "support has nothing at all to tell whoever made it."
            ),
            detail="{missing_operation}",
        ),
        "account_lists_an_operation_never_handed": observation(
            first=(
                "A copy's merge log contains a change that no packet delivered "
                "to that copy. Support cannot use a history that invents work "
                "alongside the changes it actually received."
            ),
            second=(
                "I counted the replay on your build: `{laptop}` was handed "
                "{operations_handed} changes, but its {entries_listed}-entry "
                "log also lists {unexpected_operation} as {listed_as}. That "
                "change was never delivered to that copy."
            ),
            detail="{unexpected_operation}",
        ),
        "account_places_operation_on_wrong_field": observation(
            first=(
                "Support followed one entry in the merge log back to the "
                "change it names and found it filed under a different card "
                "field. The history points them to the wrong place."
            ),
            second=(
                "On `{laptop}`, the log files {operation} under {listed_field} "
                "on {listed_card}; the delivered change actually belongs to "
                "{actual_field} on {actual_card}."
            ),
            detail="{operation}",
        ),
        "settled_operation_left_pending": observation(
            first=(
                "The log says a change is still waiting even though that "
                "laptop already has everything the change depended on. "
                "Support reads an unfinished merge where none remains."
            ),
            second=(
                "On `{laptop}`, {operation} is still marked pending for "
                "{card_field} on {card_title}, although every change it "
                "depends on has already been handed to that copy."
            ),
            detail="{operation}",
        ),
        "waiting_operation_not_pending": observation(
            first=(
                "Support paused an out-of-order replay before an earlier change "
                "had reached the laptop. The merge log already called the later "
                "change finished, even though the packet history still showed "
                "the gap."
            ),
            second=(
                "On `{laptop}`, {operation} is listed as {listed_as} for "
                "{card_field} on {card_title}, although {missing_dependency} "
                "has not been handed to that copy. The packet-by-packet account "
                "therefore says settled where the delivery record still says "
                "waiting."
            ),
            detail="{missing_dependency}",
        ),
        "account_names_a_value_the_card_does_not_show": observation(
            first=(
                "Support read a field's merge log next to the card and got two "
                "different answers about what is readable. The history they "
                "use to answer customers does not agree with the board."
            ),
            second=(
                "I put the session through again on your build and read the "
                "log next to the board: on `{laptop}` the log has "
                "{card_field} on {card_title} down as {account_says} while the "
                "card in front of me shows {card_shows}."
            ),
            detail="{account_says}",
        ),
        "edit_listed_twice_in_the_account": observation(
            first=(
                "The log double-counts. Support reads it back to a customer as "
                "the list of what happened to their work, and the same change "
                "turns up more than once, so nobody can tell whether one thing "
                "happened to their line or two."
            ),
            second=(
                "I counted on your build: on `{laptop}` the log lists "
                "{repeated_edit} {times_listed} times over, and that is one "
                "change made once by {editor}."
            ),
            detail="{repeated_edit}",
        ),
        "account_blames_an_edit_that_did_not_replace_it": observation(
            first=(
                "The merge log names a change as the reason for another "
                "entry's disposition, but the delivered work does not show "
                "that change displaced the entry. Support would assign blame "
                "that the session cannot support."
            ),
            second=(
                "I checked it on your build: on `{laptop}` the log lists "
                "{edit_named} as {listed_as} with {blamed_edit} in its `by` "
                "column for {card_field} on {card_title}, but the delivered "
                "operations do not support that account."
            ),
            detail="{blamed_edit}",
        ),
    },
}
