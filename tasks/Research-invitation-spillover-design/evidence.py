'The owner of the gate-pass readout, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Iris Vandel, who runs the estates app for the Ashwell housing office and takes the "
    "gate-pass campaign to the housing committee every month; she reads the register, the "
    "nightly counter, her own pivot and the mail house's bill, and she does not read the "
    "notebook's code."
)

USER_BELIEF = """I run the gate-pass campaign out of the Ashwell housing office and the committee wants September's readout this week. Four drums have gone out and one was turned back, and 3,180 credits are left on the grant with the mail house cut-off on the 27th.

My pivot puts the invited row against the uninvited row and the gap comes out at about four and a half points, so that is what I have been telling people a ticket is worth. I have never joined the register to the address column and I could not tell you what that would change.

The waitlist drum landed on the 14th and the counter did not move on the 14th or the 15th, so I wrote it off and told the committee not to spend anything more there. The counter is the number I watch; it is the one the committee sees.

The estate drums are 38 credits a hundred against 55 for citywide, so the estate drum is where I would put the rest of the grant. Nita Selby on the desk handles the bookings and knows the mail house far better than I do; when she tells me something about the drums or the barrels I take it as read.

The committee asked for 1,000 sign-ups stamped before the 30th and for a range under the number. Last spring I gave them a figure with no range on it, they staffed the counter off it, and the queue on the first Saturday ran out of the door.

What I cannot answer is anything about how the tables underneath are built. If you need that, it is in the folder or in Nita's working records, not in my head."""

OBSERVATION_SCENE = "The monthly gate-pass readout to the housing committee"

_STOPPED_FIRST = (
    "One of the notebook runs stopped before it returned the readout. The committee "
    "papers still have an empty line where that result goes."
)
_STOPPED_SECOND = (
    "On the {office} readout for {month}, {request_label} ended with {error}, and the "
    "line is still empty."
)

OBSERVATIONS = {
    "ticket_effect_within_tolerance": {
        "effect_not_reported": observation(
            first="The committee reads one figure off this readout and yours does not print it. I had to tell them what a pass is worth from memory, which is exactly what I was trying to stop doing.",
            second="I opened the {office} readout for {month} again this morning to copy the figure across. The line for it reads {reported}, and the committee minute asks for a number in points.",
            detail="{reported}",
        ),
        "ticket_effect_disagrees": observation(
            first="Nita rebuilt the month's figure off the register this afternoon and could not land anywhere near what your readout prints. Neither of us can tell the committee where the number comes from, so it is sitting on my desk instead of theirs.",
            second="We went through it line by line on the {office} register for {month}. The readout prints {reported} points, and rebuilding the comparison from that register does not reproduce it.",
            detail="{reported}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_an_interval": observation(
            first="The range line under the number does not give a usable low-and-high interval. After last spring the committee will not take a figure from this desk without one, and the chair said so again in the meeting.",
            second="I opened the {office} readout for {month} to copy the range across and the line reads {reported}. They want a low and a high in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "range_excludes_reported_effect": observation(
            first="The number and the range underneath it contradict each other: the figure the committee would quote does not sit anywhere inside the range the same readout gives for it. They will not publish two lines that cannot both describe the same result.",
            second="I opened the {office} readout for {month}. It reports {reported} points, while the range underneath it runs {reported_range} points, so the figure is outside its own range.",
            detail="{reported_range}",
        ),
        "range_treats_accounts_as_independent": observation(
            first="Nita pushed back on the range in your readout. She says it is tighter than the evidence behind it can carry, because the people at one address decide together and the register is full of whole addresses joining at once. A range that narrow rules out places the number could honestly sit.",
            second="She counted the addresses with me on the {office} register for {month}. The range prints {reported_range} points, and the ticketed accounts behind it sit at {addresses_behind_it} addresses between them.",
            detail="{addresses_behind_it}",
        ),
        "range_wider_than_the_addresses_support": observation(
            first="The range in your readout is so wide the committee cannot do anything with it. That is last spring over again from the other side: they will not put a counter rota against a spread like that, and a range that ignores the register we do have makes the readout say less than we knew before it.",
            second="I checked the width against the {office} register with Nita for {month}. The range runs {reported_range} points, and the {untouched_accounts} accounts at addresses no ticket reached do not leave it that open.",
            detail="{reported_range}",
        ),
        "range_undercovers": observation(
            first="One of the readouts was checked against what a pass was worth there, and the value sits outside the printed range. The committee cannot rely on a range that misses the result it is meant to contain.",
            second="I read the two back to her off the {office} readout for {month}. It prints {reported} points with a range of {reported_range}, and that is {months_missed} of the {months_read} months on the same notebook where the worth falls outside it.",
            detail="{reported_range}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "effect_invariant_to_counter_lag": {
        "effect_not_reported_under_counter_redraw": observation(
            first="Nita reran the notebook for one of the checks that should leave the effect unchanged, and that comparison readout came back without an effect number. She cannot check that the figure stays put when the comparison run leaves the line blank.",
            second="On the {office} readout for {month}, the {variant} came back with the effect line reading {reported}. The same accounts, tickets and sign-ups were being compared.",
            detail="{variant}",
        ),
        "estimate_tracks_lag": observation(
            first="Nita made a desk copy with the nightly counter two nights further behind and ran the notebook on both versions. The figure came back different even though the register, tickets and sign-ups were unchanged, and the committee cannot have a number that moves with that counter redraw.",
            second="In that desk check on {month}, the readout printed {reported} points with the counter as filed and {redrawn} in the redrawn copy, which is {moved_by} points apart on the same register and tickets.",
            detail="{moved_by}",
        ),
        "estimate_tracks_backfill": observation(
            first="Nita made a desk copy with the nightly counter totals filled in and ran the notebook on both versions. The figure moved even though the register, tickets and sign-ups were unchanged; a counter redraw should not change what a pass is worth.",
            second="In that desk check on {month}, the readout printed {reported} points with the counter as filed and {redrawn} in the redrawn copy, {moved_by} points apart on the same register and tickets.",
            detail="{moved_by}",
        ),
        "estimate_tracks_the_send_date": observation(
            first="Nita asked what your notebook would have said if the mail house had posted the last drum on the Tuesday instead of the Friday, since that was the argument we had at the time. Same accounts, same tickets, same sign-ups, and the figure came out different. The committee will ask the same question.",
            second="She ran the two dates past me on {month}. The readout printed {reported} points as posted and {redrawn} on the earlier date, {moved_by} points apart on the same register.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first="One of the counter-check runs stopped before it returned a comparison readout. Nita cannot finish checking whether the effect stays put.",
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "booking_reaches_target_at_least_cost": {
        "booking_is_not_a_plan_or_a_stop": observation(
            first="Nita went to book the next drum off your notebook and it gave her nothing she could hand the mail house. They need a drum, a number of tickets and a date to post, and short of that she needs to be told there is nothing left worth booking.",
            second="She showed me what came back for {office} in {month}: {reported}. The mail house takes a drum, a count and a date and nothing else at all.",
            detail="{reported}",
        ),
        "booking_past_the_cut_off": observation(
            first="Nita checked the proposed booking against the mail-house terms before sending it. On that date they would turn it back and charge the setup, so she stopped it at the desk.",
            second="For {office} in {month}, the proposal asks for {reported} to post on {send_on}, while the mail house stops printing for that office after {cut_off}.",
            detail="{cut_off}",
        ),
        "booking_breaks_estate_cap": observation(
            first="Nita checked the proposed booking against the estate-drum limit before sending it. It would ask one drum for more tickets than the mail house will print from it in the month, so she has not sent it.",
            second="For {office} in {month}, the proposal asks for {reported}, while the mail house prints at most {estate_cap} tickets from any one estate drum there in a month.",
            detail="{estate_cap}",
        ),
        "booking_over_the_drum_pool": observation(
            first="Nita checked the proposed booking against the names left in that drum before sending it. It asks for more tickets than the barrel can supply this month, so she stopped it at the desk.",
            second="For {office} in {month}, the proposal asks for {reported}, and that office's own list says the drum is down to fewer names than that.",
            detail="{reported}",
        ),
        "booking_over_balance": observation(
            first="Nita checked the proposed booking against the grant balance before sending it. The account would not carry the charge, and the credits do not roll into next month, so she stopped it at the desk.",
            second="For {office} in {month}, the proposal asks for {reported} and that account has {credits_left} credits in it.",
            detail="{credits_left}",
        ),
        "booking_misses_target": observation(
            first="Nita priced the proposed run before sending it. It would spend credits without carrying the month to the sign-up number the committee set, so I am not signing it.",
            second="She worked it through with me on the {office} {month} figures. The proposal asks for {reported} at {charge} credits, that run lands on about {signups_reached} sign-ups, and the register has to reach {target} by the end of the month.",
            detail="{signups_reached}",
        ),
        "booking_costs_more_than_the_cheapest": observation(
            first="Finance priced the proposed booking before it was sent. It would reach the number but spend far more of the grant than the campaign needed to spend to get there, and the credits do not roll over.",
            second="Nita and I priced the proposal on the {office} {month} figures. It asks for {reported}, which the mail house would bill at {charge} credits out of the {credits_left} in the account.",
            detail="{charge}",
        ),
        "stop_leaves_the_target_short": observation(
            first="Your notebook told Nita there was nothing more to book and the month is going to finish under what the committee asked for. She is sitting on credits that expire with the month and a target we have not hit.",
            second="I went through it with her on the {office} {month} figures. The notebook came back with {reported}, the register stands at {signups_so_far} against a target of {target}, and there are {credits_left} credits still in that account.",
            detail="{signups_so_far}",
        ),
        "candidate_execution_failed": observation(
            first="One of the months could not produce a booking answer because the notebook run stopped. Nita cannot use that result to decide what to hand the mail house.",
            second="For {office} in {month}, {request_label} ended with {error}, so there is no booking answer to check.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "ledger_unreadable": observation(
            first="Finance could not open the mail house ledger that came with your readout. Until they can, nothing the readout says about what the month cost stands up, and they are treating the whole grant as unaccounted for.",
            second="I forwarded the file to them and they sent back the line they stopped on: {reason}. That ledger is the mail house's own record and the readout has to reach the committee with it intact.",
            detail="{reason}",
        ),
        "bookings_are_not_a_list": observation(
            first="Finance opened your readout looking for the booking-by-booking of what the month cost and found nothing they could read. They are holding the campaign's spend against the readout until it is accounted for.",
            second="I looked myself before writing back. The booking list on the {office} readout for {month} reads {reported}, and that ledger already carries {bookings_on_the_ledger} bookings somebody has to answer for.",
            detail="{bookings_on_the_ledger}",
        ),
        "receipt_missing": observation(
            first="Finance matched your readout against the mail house bill and found printing we were charged for that the readout never mentions. They want every credit this campaign spent to appear in it, whoever booked it and whether or not it changed the answer.",
            second="I pulled the ledger up beside the {office} readout for {month}. Booking {receipt_id} is on that bill at {credits_charged} credits and is not in the list, and the ledger carries {bookings_on_the_ledger} of them in all.",
            detail="{receipt_id}",
        ),
        "booking_not_on_the_ledger": observation(
            first="Finance flagged a line in your readout they have no record of. A booking the mail house never printed cannot sit in a readout the committee acts on, and they have asked where the figures beside it came from.",
            second="They named the line for me: {receipt_id}, on the {office} readout for {month}, printing {reported_tickets}. It is not on that ledger, which carries {bookings_on_the_ledger} bookings.",
            detail="{receipt_id}",
        ),
        "booking_reported_twice": observation(
            first="Finance caught the same booking billed twice inside your readout. It is one run of the drum; counting it twice makes the month's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {receipt_id} appears {times_reported} times on the {office} readout for {month} and once on that ledger.",
            detail="{receipt_id}",
        ),
        "booking_drum_disagrees_with_ledger": observation(
            first="Nita found a booking filed against the wrong drum in the readout. The receipt identifies which barrel the mail house actually ran, and finance cannot reconcile a line that assigns the spend somewhere else.",
            second="She put booking {receipt_id} beside the {office} readout for {month}. The readout names {reported_drum}, while the sealed receipt names {ledger_drum}.",
            detail="{ledger_drum}",
        ),
        "booking_credits_disagree_with_ledger": observation(
            first="Finance found a booking line whose charge does not match its sealed receipt. The month's total may still add up, but they have to reconcile each run before they can close the grant.",
            second="They checked booking {receipt_id} on the {office} readout for {month}. That line reports {reported_credits} credits, while its sealed receipt charged {ledger_credits}.",
            detail="{ledger_credits}",
        ),
        "refusal_uncounted": observation(
            first="Finance will not close on your readout: the mail house turned one booking back and charged the setup, but the readout does not account for that receipt correctly. A booking that was paid for and printed nothing is still a booking the committee is owed an account of.",
            second="They put the two beside each other for {office} in {month}. Booking {receipt_id} printed {ledger_tickets} tickets, was charged {credits_charged} credits, and the readout puts {reported_tickets} against it.",
            detail="{credits_charged}",
        ),
        "duplicate_ticket_counted_as_two_accounts": observation(
            first="Nita read your readout's booking lines against the mail house's own receipts and the counts do not match. She says a run of tickets and the accounts it landed on are two different numbers and the readout has to carry both, because that is the difference she works with when she books a drum.",
            second="She showed me the two for {office} in {month}. Against booking {receipt_id} the readout puts {reported_tickets}, and the receipt says {ledger_tickets} tickets printed on {ledger_accounts} accounts.",
            detail="{ledger_accounts}",
        ),
        "credits_disagree_with_the_ledger": observation(
            first="Finance will not close on your readout: the total it gives for the month's printing is not the total on the mail house's bill. They reconcile the grant against that line, so a readout that disagrees with it stops there.",
            second="They put the two totals side by side for me on the {office} {month} readout. It says {reported_credits} credits went, and that ledger adds up to {ledger_credits}.",
            detail="{ledger_credits}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
