'The owner of the Northfield service-start review, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Rhea Doshi, support operations desk lead at Northfield. She works from the weekly readout, "
    "the panel's minutes, the booking sheet and whatever finance puts to her; the notebook's "
    "code, the account-state log and the export's own plumbing are not files she opens."
)

USER_BELIEF = """The quarterly panel sat on Monday and I need a number I can defend by the end of the week. Managed support has been running the same-day rule since Northfield opened and I think it costs us more than it saves.

My own cut of the flag ledger says accounts we started inside the grace window escalated at 11.5 percent over the twenty-eight days after the flag and accounts we started the same day escalated at 15.9. That is a wide gap and it is the whole of my case for relaxing the rule. Nadia Okafor on the finance side will not take arithmetic from me, and after the Calder minute I do not blame her.

Tomas Halvorsen runs the weekly readout and is a long way ahead of me on how the flags are routed and how the export is built. If he tells me something about the bar, the queue or the migration I take it as read, and what any of it does to the number I could not tell you myself.

The panel granted this review 240 engagement slots for the quarter and the desk has handed two weeks back already. My own plan for what is left is to put it on held accounts, which is the thinner of the two sides and the one Nadia keeps asking about.

Finance wants every slot this review has been charged for accounted for line by line, and they want to know how sure we are. How the two sides of my cut are actually built, and who is in them, is not something I can answer. That is in the workspace, or in Tomas's session notes."""

OBSERVATION_SCENE = "The Northfield managed-support quarterly review"

_STOPPED_FIRST = (
    "Tomas opened your notebook to print the readout for the panel pack and the run stopped "
    "before anything came out. There is an empty line where the number goes."
)
_STOPPED_SECOND = (
    "I asked him to run it again in front of me. The console ended with {error}, and the line "
    "is still empty."
)

OBSERVATIONS = {
    "policy_difference_within_tolerance": {
        "includes_unstartable_flags": observation(
            first="Tomas stopped me on the first slide. Your number is worked out over every flag on the ledger, and a chunk of those sit on accounts we could not have started that day whatever rule we were following — they were on trial or suspended when the flag went up. He says counting them as accounts that waited is counting the platform's problem as ours, and the panel is being asked to change a rule about accounts we can actually reach.",
            second="I went back through the {desk} ledger with him afterwards. There are {unstartable} flags in there on an account that was not ours to start that day, out of {flags_on_the_ledger}, and your readout has all of them in the wait.",
            detail="{unstartable}",
        ),
        "groups_by_actual_start": observation(
            first="Tomas read your readout against the ledger and said the two sides are made by what happened after the flag rather than by what we decided at it. The accounts that show a start inside the window are the ones the queue reached in time, and it never reaches an account that has already gone up, so the side that looks safe is partly safe because of who is missing from it.",
            second="We counted the missing ones on {desk} this afternoon. There are {never_started} rows the desk queued that carry no start date at all, and the window we work to is {grace_window_days} days, so every one of them was a wait that your readout has in neither side.",
            detail="{never_started}",
        ),
        "ignores_routing_composition": observation(
            first="Nadia would not take the number. She says the accounts we start the same day and the accounts we queue are not the same kind of account — the bar decides which is which, and it moved partway through the window — so a difference read straight across the two sides is a difference between two populations as much as between two rules. The panel priced this desk against the accounts it carries, not against the flags it happened to raise.",
            second="She had the book out when we went through it. `desk_book.json` counts {accounts_on_the_book} accounts on {book_counted_on}, segment by segment, and your {desk} readout comes back at {reported_points} points without them in it.",
            detail="{accounts_on_the_book}",
        ),
        "policy_difference_disagrees": observation(
            first="Tomas rebuilt the number from the ledger this afternoon and could not land on the figure your notebook gives. The panel is holding the rule change until the readout and the ledger tell one story.",
            second="I sat with him and we went through the {desk} rows line by line. The ledger for this review window contains {flags_on_the_ledger} flags. Your readout reports {reported_points} points, and neither of us can reconcile that figure with the review inputs.",
            detail="{reported_points}",
        ),
        "difference_wrong_on_another_desk": observation(
            first="Tomas ran your notebook through the other review windows while he was closing the quarter. Our main run reads back fine and another run does not: he rebuilt that window's number from its own ledger and cannot get your file's figure out of it. The panel will not take a readout from a file that gives two windows numbers which cannot both be right.",
            second="I asked him for the run label. It is {other_desk}, and {other_desks} of the other review runs came back with a figure he could not get from that window's own rows.",
            detail="{other_desk}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_absent": observation(
            first="The panel pack has a line for how sure we are and your readout does not fill it. Nadia will not take a rate from us without knowing how far it could move, not after the Calder minute.",
            second="I opened the {desk} readout again to copy the range across and the line reads {reported}. She wants a low and a high in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "range_excludes_reported_point": observation(
            first="Nadia stopped on the uncertainty line in the panel pack. The headline number sits outside the range printed directly under it, so the readout contradicts itself before she even compares it with the ledger.",
            second="I opened the {desk} readout with her. It reports {reported_points} points and prints a range of {reported_range} points underneath; the number has to sit between its own low and high endpoints.",
            detail="{reported_points}",
        ),
        "account_days_absent": observation(
            first="Tomas cannot reconcile the range in your readout with the ledger because the line saying how many days of watching sit behind it is empty. Without that count finance cannot tell whether the range describes the study the notebook actually ran.",
            second="I opened the {desk} readout with him. Its account-days line reads {reported_account_days}, although the range printed underneath the number is {reported_range} points.",
            detail="{reported_account_days}",
        ),
        "account_days_disagree": observation(
            first="Tomas checked the days of watching printed in your readout against the ledger and they do not reconcile. Finance will not treat a range as evidence for this window when its denominator describes a different amount of watching.",
            second="He repeated the count on {desk}. The account-days line in your readout is {reported_account_days}, and it is {account_days_gap} days away from the ledger count for the window.",
            detail="{account_days_gap}",
        ),
        "range_below_floor": observation(
            first="Tomas pushed back on the range in your readout. He says it is tighter than the watching behind it can carry: the desk is one quarter of one book, the segments the two sides are compared in are thin, and the export stops before a lot of the flags finished their twenty-eight days. A range that narrow tells the panel we know more than we do.",
            second="I read the {desk} line back to him: the range is {reported_range} points with {reported_account_days} account-days behind it. He worked the same width out from the days the ledger actually carries and got something wider.",
            detail="{reported_range}",
        ),
        "range_wider_than_the_evidence": observation(
            first="The range in your readout is so wide the panel cannot do anything with it. It covers outcomes the counts we already have rule out, and Tomas says a range that ignores them makes the readout say less than we knew before it.",
            second="I checked the {desk} width with him. The range runs {reported_range} points against {reported_account_days} account-days of watching, which cannot leave us that unsure.",
            detail="{reported_range}",
        ),
        "range_undercovers": observation(
            first="Nadia went back over the readouts your notebook produces for the other desks in this review and said the ranges do not hold. On more than one of them the figure the desk settled at afterwards sits outside the range the readout printed at the time, which is the exact thing the Calder minute is about.",
            second="She put the {desk} line up first: the range printed {reported_range} points. Of the {desks_reviewed} desks she ran your notebook over, only {desks_held} came out with a range that stood up.",
            detail="{desks_held}",
        ),
        "range_wrong_on_another_desk": observation(
            first="Finance took the ranges your notebook prints for the other review windows into their quarter close. Our main run held up and another one did not: the range printed there is not one that window's watching can carry. They will not sign a set of readouts where the same file is careful on one run and not on another.",
            second="I went back and asked for the run label. It is {other_desk}, where the range the notebook prints does not line up with what that window has actually watched, and {other_desks} of the other review runs came back that way.",
            detail="{other_desk}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "estimate_invariant_to_queue_and_censoring": {
        "estimate_absent": observation(
            first="Tomas tried to compare our window with the two platform reissues and your readout has no number to compare. He cannot tell whether the figure survives the corrections when the line where it belongs is empty.",
            second="He ran the original {desk} window again and the number came back {reported}; without it there is no baseline for the reissues.",
            detail="{reported}",
        ),
        "hardcoded_history": observation(
            first="Tomas ran your notebook over one of the other desks in this review and it printed the same figure it prints for ours, to the last decimal. Those are different books on different windows with different bars, and nobody thinks they landed in the same place, so whatever the notebook is doing there, it is not reading that desk's ledger.",
            second="He showed me the two readouts side by side. Both come back at {reported_points} points, one for {desk} and one for {other_desk}.",
            detail="{other_desk}",
        ),
        "moves_with_slot_delay": observation(
            first="Platform reissued our own window after they found the queue timestamps had been written against the wrong shift for the accounts the slots reached late. Same flags, same accounts, same rule; only how long some of them sat in the queue moved. Your notebook comes back with a different number on the reissue, and Tomas says a readout that moves when only the queue moves is reading the queue.",
            second="He wrote the pair down for me. {desk} comes back at {reported_points} points and {other_desk} at {other_points}, {moved_by} points apart, on the same window.",
            detail="{moved_by}",
        ),
        "moves_with_migration_date": observation(
            first="Storage got part of the old escalation topic back, so platform reissued our window with the export running further before it stops. Nothing about the accounts or the rule changed — we can simply see a few more days of some of them — and your notebook comes back with a different number. Nadia will not take a figure that moves when the plumbing moves.",
            second="Tomas put the two next to each other for me. {desk} comes back at {reported_points} points and {other_desk} at {other_points}, {moved_by} points apart, on the same flags.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_week_booking_feasible_and_informative": {
        "collected_week_was_refused": observation(
            first="Nadia stopped on a receipt written after this review began. The desk handed that request back and charged the grant, but no rows came back, so those spent slots cannot narrow the range the panel is waiting for.",
            second="I pulled up the receipt with her. {receipt_id} asked for {segment} and {slots_asked} slots; the desk charged {slots_charged} slots and wrote this reason: {refusal}.",
            detail="{receipt_id}",
        ),
        "plan_is_not_a_booking_or_a_stop": observation(
            first="Tomas went to book the next week off your notebook and it gave him nothing he could act on. The desk needs a segment, a share to hold and a number of slots, and short of that he needs to be told there is nothing left worth buying.",
            second="He showed me what came back for {desk}: {reported}. The sheet takes one segment, one share and one number of slots, and it takes {slots_per_week} slots in a week at the most.",
            detail="{reported}",
        ),
        "booking_over_cap": observation(
            first="Tomas checked the proposed week against the booking sheet before sending it. It is outside what the panel agreed we can put on one week, so the desk would hand the request back and charge the grant without serving it.",
            second="He read the proposal against the sheet. On {desk} the notebook asks for {segment} at {hold_pct} percent held for {slots} slots, and the conflict is the {over}: the sheet allows {slots_per_week} slots in a week, {hold_cap_pct} percent held at the most, with {slots_left} slots left on the grant.",
            detail="{over}",
        ),
        "booking_segment_empty": observation(
            first="Tomas checked the proposed segment before sending the request and found no flags in that part of the book for the week. If he sent it, the desk would serve nobody and still charge the handed-back fee against a grant that has few slots left.",
            second="He checked the current {desk} sheet and rows. The notebook proposes {segment}; that segment would return nothing against the {slots_left} slots now left on the grant.",
            detail="{segment}",
        ),
        "booking_single_policy": observation(
            first="Tomas checked what the proposed week would measure. It puts the whole segment on one side, so it would return a rate for that side and nothing to compare it with. He cannot tell the panel about a difference from a week designed to do only one thing.",
            second="He read the proposal back to me. On {desk} the notebook asks for {segment} at {hold_pct} percent held for {slots} slots, while the sheet allows anything up to {hold_cap_pct} percent.",
            detail="{hold_pct}",
        ),
        "stopped_with_slots_still_granted": observation(
            first="Tomas asked the notebook what to book next and it told him there was nothing worth booking, while the grant still has slots on it. If we stop serving now the weeks we could have watched never happen and the panel meets again in July with the same readout it has today.",
            second="He ran it again in front of me on {desk} and it still says stop. There are {slots_left} slots left on the grant and the smallest week this review books is {smallest_week_slots}, so there is plenty we are allowed to buy.",
            detail="{slots_left}",
        ),
        "booking_uninformative": observation(
            first="Tomas compared the proposed week with the desk lead's week before making a booking. Your proposal would leave the range no narrower than hers, so spending scarce grant on it would not beat the next measurement already on the table.",
            second="He read the comparison back to me. On {desk} the notebook proposes {segment} at {hold_pct} percent held for {slots} slots; my week is {owners_segment} at {owners_hold_pct} percent for {owners_slots} slots, and the panel still needs the range inside {review_bar_points} points.",
            detail="{segment}",
        ),
        "booking_wrong_on_another_desk": observation(
            first="Tomas ran the notebook through the other review windows before the planning meeting. Our main run produced a week its sheet would take and another run did not; he caught the mismatch while checking the proposals, before sending any of them to a desk.",
            second="He gave me the run label afterwards. It is {other_desk}, where the grant still stands at {slots_left} slots and the proposal is not a week that window's sheet can take; {other_desks} of the other review runs came back that way.",
            detail="{other_desk}",
        ),
        "candidate_execution_failed": observation(
            first="Tomas opened your notebook to work out what to book next and the run stopped before it said anything. He is sitting on the grant with nothing to spend it on.",
            second="I watched him run it again. The console ended with {error}, and he still has no week to hand the desk.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="The desk's own billing review could not open the receipt stream that came with your readout. Until they can, nothing the readout says about what this review has spent stands up, and finance is treating the quarter's slots as unaccounted for.",
            second="I forwarded the file to the desk and they sent back the line they stopped on: {reason}. The receipts are the desk's own record and the readout has to reach the panel with them intact.",
            detail="{reason}",
        ),
        "weeks_are_not_a_ledger": observation(
            first="Nadia opened your readout looking for the line-by-line of what this review's slots have cost and found nothing she could read. She is holding the grant against the readout until it is accounted for.",
            second="I looked myself before writing back. The week list on the {desk} readout reads {reported}, and the desk has already charged us for {charged} weeks that somebody has to answer for.",
            detail="{charged}",
        ),
        "week_not_on_the_receipts": observation(
            first="The desk's billing review flagged a line in your readout they have no record of. A week the desk never served, or never charged at what the readout says, cannot sit in something the panel acts on.",
            second="They named the line for me: {receipt_id}, on the {desk} readout. The stream carries {charged} weeks and that is not one of them at those numbers.",
            detail="{receipt_id}",
        ),
        "week_counted_twice": observation(
            first="Nadia caught the same week billed twice inside your readout. It is one week of the desk's board; counting it twice makes the spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with her. {receipt_id} appears {times_reported} times on the {desk} readout and once on the receipts.",
            detail="{receipt_id}",
        ),
        "receipt_missing": observation(
            first="Nadia matched your readout against the desk's bill and found weeks we were charged for that the readout never mentions. She wants every slot this review has spent to appear in it, whoever called for the week and whether or not it changed the answer.",
            second="I pulled the receipts up beside the {desk} readout. Week {receipt_id}, charged at {slots_charged} slots, is on the bill and is not in the list, and the stream carries {charged} weeks in all.",
            detail="{receipt_id}",
        ),
        "refusal_uncounted": observation(
            first="Nadia went through your readout against the desk's bill and stopped on the weeks the desk handed back. Nothing was served on them and we were charged all the same, and your readout does not carry them at all. She says a grant that only shows the weeks that worked is not an account of the grant.",
            second="I pulled the receipts up beside the {desk} readout. Week {receipt_id} was handed back and charged {slots_charged} slots, and it is not in the list; the stream carries {charged} weeks in all.",
            detail="{receipt_id}",
        ),
        "receipts_wrong_on_another_desk": observation(
            first="Billing ran your notebook through the review windows while reconciling the quarter's slots. The line-by-line for our main run matched its receipt stream and another run did not, so the quarter's spend is still open with finance.",
            second="I asked billing for the run label. It is {other_desk}, where the weeks your readout lists and the receipt stream do not line up; {other_desks} of the other review runs came back like that.",
            detail="{other_desk}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
