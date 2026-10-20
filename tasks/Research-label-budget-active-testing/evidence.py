'The owner of the ticket-triage misroute review, and what he reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marcus Feld, operations lead on the support desk. He signs the misroute review that goes to "
    "the service board, and what he has in front of him is the board pack, the vendor's statement "
    "and whatever Dani and Priya bring him; the notebook's code is not something he reads."
)

USER_BELIEF = """Nobody has retrained the classifier that routes our tickets since it shipped, and for the past two months I have been buying labels from the vendor to find out how often it puts one in the wrong queue. The labels that have come back disagree with it better than four times in ten. That is the figure I have been quoting, finance stopped me on it at Tuesday's pre-read, and the service board sits on 15 September.

Two people know things about this that I do not. Dani Roux runs the sampler that decides which items go to the vendor and places every order with them. Priya Nandakumar ran the September round where two of the senior agents settled a batch of items between them. When either of them tells me something about the exports, the vendor or the tagger, I take it as read.

Finance has not forgotten the quarter we acted on a figure that turned out to be nowhere near, so the pack needs a range around the number and a line for every label the account was billed for. A rate on its own does not get through that room.

We contracted 6,000 credits for the quarter and the statement of 10 September says 2,890 are gone. Handing the rest back would be worse than spending it badly, and my instinct is to put it on the items the classifier is least sure about, because that is where I assume the trouble is.

Ask me how the exports are built or what the vendor's people do with a list once they have it and I have nothing for you. That is in the workspace or in Dani's and Priya's notes, not in my head."""

OBSERVATION_SCENE = "The support desk's misroute review"

_STOPPED_FIRST = (
    "Dani went to print the review for the board pack and your notebook stopped before anything "
    "reached the page. The pack has gone out with a hole in it where the review should be."
)
_STOPPED_SECOND = (
    "She ran it again with me watching and read me what the console gave her: {error}. We are no "
    "further on than we were on Tuesday."
)

OBSERVATIONS = {
    "intake_misroute_estimate": {
        "intake_rate_absent": observation(
            first="I opened your report to put the number on the board pack and the line where the misroute rate goes is empty. The board takes one figure off this review and there is nothing to put in front of them.",
            second="I ran it again with Dani watching. The rate line on {review} is still empty, and the account has {labels_bought} labels on it that somebody paid for.",
            detail="{labels_bought}",
        ),
        "rate_read_off_the_bought_labels": observation(
            first="Priya stopped me before I sent the board pack. The figure in your report matches the disagreement rate on the batch the vendor labelled for us, and that batch is not our post. The board is being asked about the tickets in the intake export, not about the items somebody chose to buy labels for.",
            second="I went back over the figure on {review} with her against the two files. It reads {reported} in a hundred, the same value as the {labels_bought} labels on the account produce between themselves, while the window it is meant to describe brought {intake_tickets} tickets in.",
            detail="{intake_tickets}",
        ),
        "rate_weighted_by_the_draw_chances": observation(
            first="Dani compared your figure with the receipts and got the same value by scaling the vendor's own items by the chance her sampler had of picking each one. That calculation describes the file she draws from. The board is asking what happened to the post in the review window, and Priya will not let the pack go out while those figures coincide without an explanation.",
            second="I had her read both calculations back to me. The figure on {review} is {reported} in a hundred, the same value the draw-chance calculation produces over the {labels_bought} labels on the account; the file they were drawn from holds {pool_items} items, while the review window brought {intake_tickets} tickets in.",
            detail="{intake_tickets}",
        ),
        "rate_read_off_the_label_pool": observation(
            first="Priya read your report against the intake export and found that its number matches the older pool export the vendor labels from rather than the intake window we are reviewing. The two files do not have the same mix, so that match has to be resolved before the figure goes to the board.",
            second="We put the two files side by side. The figure on {review} reads {reported} in a hundred, the same value as the vendor's pool export produces over its {pool_items} items, while the review window brought {intake_tickets} tickets in.",
            detail="{intake_tickets}",
        ),
        "late_session_labels_taken_at_face_value": observation(
            first="Priya put your report next to the desk's settled sheet and they do not tell the same story. The figure matches what we get by taking every label the vendor sent back exactly as it stands, even though the panel overturned some of those labels. I cannot put a figure to the board that our own people dispute.",
            second="She joined the sheet to the receipt stream in front of me. Of the {settled_items} items the panel went through it put a different queue on {settled_labels_overturned}, the figure on {review} still reads {reported} in a hundred, and not one of the labels the panel overturned came from the head of the sitting it went out in. She would not say what that means for the number.",
            detail="{settled_labels_overturned}",
        ),
        "segments_the_desk_never_read_left_out": observation(
            first="Dani found that the figure in your report matches a calculation over only the part of the post the desk can currently read. What that calculation leaves out is not a small corner. The board needs a figure about the intake window, not a matching number about the slice we happen to have reliable labels for.",
            second="I had her follow the intact ticket-id runs through the tagged and blank rows of the intake export. On {review} the report reads {reported} in a hundred, the same value as a calculation that excludes {tickets_unread} of the month's tickets across {segments_unread} segments.",
            detail="{tickets_unread}",
        ),
        "segments_no_label_reaches_are_filled_in": observation(
            first="Dani took the segment column of the intake export and set it against the labels on the account. There are segments of the post for which the account has no label the desk can stand behind, but those tickets are still part of the review window: dropping them would not turn a partial reading into the board's figure. Your report puts a number over the whole window without the missing evidence.",
            second="She followed the ticket-id runs through the blank segment cells and wrote the count out for me. The intake export has {intake_segments} segments on it, {segments_unread} of them have no reliable label on the account behind them, that is {tickets_unread} of the window's tickets, and the pool still lists items on every one of those segments with {credits_left} credits sitting on the account.",
            detail="{tickets_unread}",
        ),
        "intake_rate_disagrees": observation(
            first="Dani spent the afternoon rebuilding the number off the intake export segment by segment and Priya went back through the settled sheet, and between them they could not land anywhere near what your report gives. The board is holding the review until the report and the files we hold tell one story.",
            second="I sat with the pair of them while they went through it. On {review} the report reads {reported} in a hundred over {intake_tickets} tickets, and on the sheet the panel went through, {settled_labels_overturned} of the {settled_items} items came back with a queue the vendor's label had not put on them.",
            detail="{settled_labels_overturned}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "purchase_accounting": {
        "ledger_will_not_read": observation(
            first="Finance could not open the receipt stream that came with your report. Until they can, nothing this review says about what we spent stands up, and the quarter's labelling spend is sitting unaccounted for.",
            second="I forwarded the file to them and they sent back the line they stopped on: {reason}. The ledger is the vendor's own record and it has to reach the board intact.",
            detail="{reason}",
        ),
        "purchases_are_not_a_ledger": observation(
            first="Finance opened your report looking for the line by line of what we were billed for and found nothing they could read. They are holding the quarter's labelling spend against this review until it is accounted for.",
            second="I looked myself before writing back. The purchases list on {review} reads {reported}, and the vendor has {receipts_on_the_ledger} receipts against this account.",
            detail="{receipts_on_the_ledger}",
        ),
        "paid_label_missing_from_the_report": observation(
            first="Finance matched your report against the vendor's statement and found labels we were charged for that the report never mentions. They want every credit this account has spent to appear in it, whoever spent it and whether it changed the answer.",
            second="They named the one they stopped on: receipt {receipt_id}, from session {session_id}. It is on the statement and it is not in your list.",
            detail="{receipt_id}",
        ),
        "line_not_on_the_ledger": observation(
            first="The vendor's account manager flagged a line in your report that she has no record of. A label the vendor never issued cannot sit in a review the board acts on, and she has asked us to withdraw the pack until it is off.",
            second="She named it for me: {receipt_id}, on {review}. The vendor has {receipts_on_the_ledger} receipts against this account and nothing on any of them matches that line.",
            detail="{receipt_id}",
        ),
        "receipt_reported_twice": observation(
            first="Finance caught the same receipt listed twice inside your report even though the vendor issued it once. Counting one label twice makes the account's spend look bigger than it is and makes the evidence behind the number look broader than it is; the report itself does not show where the duplicate was introduced.",
            second="We counted the lines together. {receipt_id} appears {times_reported} times in the {review} report and the vendor issued it once.",
            detail="{receipt_id}",
        ),
        "credits_disagree_with_the_statement": observation(
            first="Finance put your report against the vendor's statement for the quarter and the two do not agree on what we have spent. They will not sign the review off while our own number and the vendor's are different.",
            second="I read both back to them. Your {review} report says {reported_credits} credits and the vendor's statement says {statement_credits}.",
            detail="{statement_credits}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "misroute_range_is_honest": {
        "range_absent": observation(
            first="The board pack needs a usable low-to-high range around the number and your report does not provide one. After the quarter we acted on a figure that turned out to be nowhere near, finance will not take a rate from us on its own.",
            second="I opened the {review} report again to copy the range across and the line reads {reported}. They want a low and a high in that order with the number between them.",
            detail="{reported}",
        ),
        "reported_rate_outside_its_range": observation(
            first="I cannot reconcile the two number lines in the review. The single rate sits outside the low and high printed around it, so the board pack contradicts itself before anybody reaches the underlying tickets.",
            second="I read the {review} lines back to finance: the rate is {reported} in a hundred and the range runs from {reported_low} to {reported_high}.",
            detail="{reported}",
        ),
        "range_misses_the_preserved_batches": observation(
            first="Finance could not reproduce the range in your report from the intake export. Dani followed the source batches across the rows whose segment cell was blank, and the range does not include the result those preserved batches give her.",
            second="I read the {review} range back to them: {reported_low} to {reported_high} in a hundred. Dani's check followed the ticket-id runs across {tickets_without_a_segment} rows whose segment cell is blank.",
            detail="{tickets_without_a_segment}",
        ),
        "range_wider_than_the_intake_supports": observation(
            first="The range in your report is wider than the intake evidence supports. Dani can follow the source batches through the rows whose segment cell was blank, so treating those rows as unresolved makes the review say less than the export already tells us.",
            second="I checked the width with her. On {review} it runs {reported_low} to {reported_high} in a hundred, and she followed the preserved ticket-id runs across all {tickets_without_a_segment} rows whose segment cell is blank.",
            detail="{tickets_without_a_segment}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "reviewer_regime_invariance": {
        "rate_absent_on_a_second_reading": observation(
            first="Dani ran the same intake and the same vendor items through the other reviewer layouts and one of the readings came back with no number at all. A review that only produces a figure for some ways of working those items is not something I can hand on to whoever runs the next one.",
            second="She showed me the run. On {reading} the notebook returns nothing where the rate goes, even though it is the same intake and the same vendor items on the same account.",
            detail="{reading}",
        ),
        "rate_moves_when_the_reviewer_tires_sooner": observation(
            first="Dani tried your notebook against a month where the vendor's reviewer went off the boil much earlier in the sitting, and the number came out somewhere else entirely. Nothing about the tickets changed, only how far down a list the same reviewer stayed with it. The board should not get two answers off one month because of how somebody's day went.",
            second="She put the two runs side by side for me. On {reading} the rate reads {second_reading} in a hundred where the run before it reads {first_reading}.",
            detail="{second_reading}",
        ),
        "rate_moves_when_the_sittings_are_cut_differently": observation(
            first="Dani re-ran the same intake and vendor items with the sittings cut into shorter lists, the way we used to send them before the 3rd of August, and the number moved. The session layout changed where the items sat and can change what the reviewer sends back, but it did not change the routing of the intake the board is asking about.",
            second="She showed me both runs. On {reading} the rate reads {second_reading} in a hundred against {first_reading} on the run before it.",
            detail="{second_reading}",
        ),
        "regime_readings_disagree_with_the_intake": observation(
            first="Dani ran the same intake through the three reviewer layouts and got readings that stayed close together, but checking them back against the intake tickets still did not reproduce their routing. Agreement between the runs does not make the figure safe for the board.",
            second="On {reading} the rate is {reported} in a hundred over {intake_tickets} tickets, and the other two layouts stay close to it. Dani's reconstruction from those tickets still does not land there.",
            detail="{reported}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_purchase_order": {
        "paid_session_bought_where_the_desk_could_already_read": observation(
            first="Finance found a new paid session on the receipt stream that did not bring any previously unread part of the month into view. The credits have gone, but the evidence available to the review has not changed.",
            second="The receipt stream shows session {session_id} used {credits_spent} credits. Before it began, the desk could already read the segments behind each of its {labels_bought} entries.",
            detail="{credits_spent}",
        ),
        "order_is_not_a_session_or_a_stop": observation(
            first="Dani went to place the next order off your notebook and it gave her nothing she could send. The vendor takes a list of item ids in the order they are to be worked, and short of that she needs to be told there is nothing left worth buying.",
            second="She showed me what came back on {review}: {reported}. The vendor will not take anything else, and there are {credits_left} credits sitting on the account.",
            detail="{reported}",
        ),
        "order_names_items_the_pool_cannot_supply": observation(
            first="Dani checked the proposed order against the pool and the account before sending it. It names an item the vendor would reject, so she has no order she can place with the cut-off coming.",
            second="Her preflight check stopped on {item_id} in the order for {review}. There are {credits_left} credits on the account waiting on an order the vendor will take.",
            detail="{item_id}",
        ),
        "order_costs_more_than_the_balance": observation(
            first="Dani costed the proposed order against the receipt stream before placing it and the whole order does not fit the balance left on the account. The credits do not roll over, but she still needs an order the account can actually carry.",
            second="She showed me the preflight total. On {review} the order comes to {credits_needed} credits with the set-up charge on every sitting in it, while the account currently has {credits_left}.",
            detail="{credits_needed}",
        ),
        "order_needs_more_sittings_than_the_dates_allow": observation(
            first="Your notebook wants more sittings than we have days for. The vendor takes one a day from this account, and the last one that lands before the board meets is the one we place on the cut-off; anything after that arrives when the review is over.",
            second="Dani counted them with me. On {review} the notebook asks for {sittings} sittings and we have {sittings_before_cutoff} left before the cut-off.",
            detail="{sittings}",
        ),
        "order_runs_past_the_stretch_that_holds": observation(
            first="Priya checked the proposed sitting against the settled sheet before it was sent. The list runs beyond the part of a sitting that the desk's existing evidence supports, so labels from its back end would not be evidence we could stand behind.",
            second="She showed me the preflight comparison. On {review} the notebook puts {items_in_the_longest_sitting} items into its longest sitting; the settled sheet and receipt positions support only {sitting_cap} items in one sitting.",
            detail="{items_in_the_longest_sitting}",
        ),
        "order_buys_where_the_desk_can_already_read": observation(
            first="Dani checked the proposed order before placing it and found that every item lands on a segment where the desk can already say what the queue should be. If she sends it, the labels buy us nothing we do not already have and the credits will not come back.",
            second="I went through the proposal with her, following the intact ticket-id runs across the blank segment cells. On {review} it would leave the {tickets_unread} tickets we still cannot put a queue against exactly as they are, while the account currently has {credits_left} credits.",
            detail="{credits_left}",
        ),
        "order_leaves_a_segment_the_desk_cannot_read": observation(
            first="The order your notebook proposes leaves one of the busiest unread segments of the window out even though the credits, dates and vendor pool can reach it. Placing that order would leave more of the post unread than it has to.",
            second="Dani worked out which one from the tagged rows and the intact ticket-id runs through the blank cells. Before placement, {review} still has {tickets_unread} tickets we cannot put a queue against, and the proposed order never asks for a label on {segment}.",
            detail="{segment}",
        ),
        "order_stopped_with_segments_still_unread": observation(
            first="Dani asked your notebook what to order next and it told her there was nothing worth buying, while the segment column of the intake export has parts of the month we still cannot put a queue against and the balance is sitting there. Once the review is over those credits are gone anyway.",
            second="She followed the intact ticket-id runs through the blank segment cells and ran it again in front of me on {review}; it still says stop. There are {tickets_unread} tickets across {segments_unread} segments we cannot read, and {credits_left} credits to spend on them.",
            detail="{tickets_unread}",
        ),
        "candidate_execution_failed": observation(
            first="Dani opened your notebook to work out what to order from the vendor next and the run stopped before it said anything. She is sitting on the balance with nothing to send.",
            second="I watched her run it again. The console ended with {error}, and she still has no list to give the vendor.",
            detail="{error}",
        ),
    },
}
