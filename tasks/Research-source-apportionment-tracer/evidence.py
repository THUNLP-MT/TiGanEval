'The owner of the Block A apportionment, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Nadia Kolb, energy manager for estates. She works from the sample sheet, the "
    "characterisation sheet, the director's note and whatever the analyser desk tells her; "
    "the notebook's code, the visit receipts and the heat meter's own file are not things "
    "she opens."
)

USER_BELIEF = """The Block A header takes three supplies — the district tie-in, the gas plant and the data-hall recovery — and the director wants January's split between them by the 12th. Both contract renewals hang on it. The recovery contract is billed on the recovery share and finance will not sign the invoice unless the range on it is inside two in a hundred either side; the gas renegotiation needs the three figures good to four in a hundred.

The report I have is mine. I wrote `analysis.py` off the characterisation sheet while the round was still going out, and it comes back at two fifths district, two fifths gas, a fifth recovery. Gas are quoting off that same two fifths, which is the part I would like somebody to stand behind before I sign.

There are fourteen slots left on the analyser agreement and five days in February the desk will still serve. My own instinct is to spend them on more header slots: thirteen slots is a thin month and another dozen would tighten the average.

Owen Petrakis draws the round and Priya Sandoval runs the reporting side. If Priya tells me something about the analyser, the floors or the desk I take it as read, and what any of it does to the figures I could not tell you myself.

How the sample sheet turns into three fractions, and which slots belong in it, is not something I can answer. That is in the workspace, or in Owen's and Priya's session notes."""

OBSERVATION_SCENE = "The January apportionment for Block A"

_STOPPED_FIRST = (
    "Priya ran your notebook across the reporting stack while she was closing the director's "
    "pack, and one of the requested reports stopped before it returned a line. She cannot close "
    "the batch while the same notebook fails on one of its windows."
)
_STOPPED_SECOND = (
    "I asked her to run the reporting batch again in front of me. The failed run ended with "
    "{error}, and the batch still does not complete."
)

OBSERVATIONS = {
    "supply_shares_within_tolerance": {
        "shares_are_not_three_numbers": observation(
            first="The director opened your report looking for the three shares and could not find figures in it. He needs one fraction against each supply and nothing else will do; the gas renegotiation is on his desk this week.",
            second="I looked myself before writing back to him. The line where the three supplies go reads {reported}, and he is expecting a fraction against each of the three the header takes.",
            detail="{reported}",
        ),
        "shares_do_not_add_to_one": observation(
            first="The director added the three fractions in your report and they do not make the whole month. He cannot put more or less than all of Block A's delivered heat across the three contracts, so the renegotiation is back on hold.",
            second="I checked the arithmetic on the {window} report myself. The three fractions add to {reported_total}, rather than one whole month.",
            detail="{reported_total}",
        ),
        "shares_use_sheet_signature": observation(
            first="Priya stopped me on the first line of your report. She says the characterisation sheet is one morning's reading at the tie-in station and the tie-in does not hold still: the operator doses the makeup rig off the outdoor sensor, and January was nothing like the day the sheet was read. The split follows the pattern she gets when that mild morning is allowed to stand for the month, and the director cannot renegotiate gas on that basis.",
            second="I sat with the {window} numbers again afterwards. Your report puts the {supply} share at {reported_share}, and Priya had the sheet out beside the weather log: it was read on {sheet_day} at {sheet_outdoor_C} degrees and the month went down to {coldest_C}.",
            detail="{reported_share}",
        ),
        "shares_include_changeover_rows": observation(
            first="Owen read your report against his own round and said the figures follow the pattern he gets when he keeps slots drawn while the plant room was mid-changeover. The board has the times on it. Whatever was in the header for those two hours, he says it was not the three supplies we bill for, and the director needs a January split that does not lean on them.",
            second="We went back through the {window} sheet with the board next to it. Your report has the {supply} share at {reported_share}, and there are {samples_in_the_window} slots on the sheet drawn while an entry on the board was open, starting with {first_sample}.",
            detail="{first_sample}",
        ),
        "shares_unweighted_samples": observation(
            first="Priya read your report against the heat meter and pulled a face. The contractor draws his round on the days he is on site, and the meter says those days are nowhere near equal — one of them delivered two and a half times what another did. The split follows the pattern she gets when every sampled day is given the same say, so it describes the days Owen happened to be on the roof rather than the heat the block received.",
            second="She put the {window} figures next to the meter for me. Your report has the {supply} share at {reported_share}; {heaviest_day} delivered two and a half times the heat that {lightest_day} did, and the reported split lines up with giving both days the same say.",
            detail="{reported_share}",
        ),
        "shares_spent_the_grant_before_reading_the_rate": observation(
            first="Priya went back to the desk to book the last of the agreement and there is nothing on it. The season's slots are gone and the February days with them, and the split your notebook prints is still not one she can rebuild from the sheet. The director is being asked to renegotiate gas off a figure nobody can go back and check now.",
            second="I asked the desk what we spent it on. Of this window's grant, {slots_on_the_header} slots went on header rounds across {visits_on_the_ledger} visits and the tie-in station was never opened; your report has the {supply} share at {reported_share}, and there is nothing left on the agreement that could settle it.",
            detail="{slots_on_the_header}",
        ),
        "shares_disagree": observation(
            first="Priya rebuilt the January split from the sheet this afternoon and could not land on the same figures your notebook gives. The director is holding the gas renegotiation until the report and the sheet tell one story.",
            second="I sat with her and we went through the {window} numbers line by line. Your report comes back with the {supply} share at {reported_share}, and neither of us can get the sheet to give that inside the {tolerance} the director asked for.",
            detail="{reported_share}",
        ),
        "shares_elsewhere_lean_on_the_sheet": observation(
            first="Priya ran your notebook over the other windows on the stack while she was closing the quarter. Ours reads back fine and one of the others does not, and its split follows the same pattern she gets when that window's characterisation sheet is allowed to stand for the month. A sheet is one morning at the station, while the operator doses the makeup rig off the outdoor sensor. The director will not take a January figure from a notebook whose other reports lean on one morning that way.",
            second="I asked her which window it was. It is {other_window}, where your file comes back with {other_reading}; its sheet was read on {sheet_day} at {sheet_outdoor_C} degrees and that month went down to {coldest_C}, and {other_windows} of the ones she ran the same file over came back the same way.",
            detail="{other_reading}",
        ),
        "shares_wrong_on_another_window": observation(
            first="Priya ran your notebook over the other windows on the stack while she was closing the quarter. Ours reads back fine and one of the others does not: she cannot reconcile the split your file prints there with that window's own reporting records. The director will not take a January figure from a notebook that cannot read two windows consistently.",
            second="I asked her which window it was. It is {other_window}, where your file comes back with {other_reading}; Priya cannot reconcile that line with the window's own records, and {other_windows} of the ones she ran the same file over came back that way.",
            detail="{other_reading}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "band_covers_and_meets_floor": {
        "band_is_not_a_range": observation(
            first="Finance came back on your report within the hour. The billing clause on the recovery contract needs a low end and a high end against that share, and there is nothing they can read on that line. Without it they will not sign the January invoice at all.",
            second="I opened the {window} report again to copy the range across for them and the line against {supply} reads {reported}. They want a low and a high in that order with the share sitting between them.",
            detail="{reported}",
        ),
        "band_excludes_reported_share": observation(
            first="Finance cannot reconcile the recovery line inside your own report. The recovery fraction sits outside the low and high printed beside it, so they cannot tell which number the contract is meant to be billed on.",
            second="I read the {window} line back to them. The {supply} fraction is {reported_share}, while its range is {reported_band}; the fraction is not between those two ends.",
            detail="{reported_share}",
        ),
        "band_tighter_than_the_floor": observation(
            first="Priya pushed back hard on the range in your report. She says the recovery line on the characterisation sheet is not a number at all — the analyser never printed one for it, it printed a bound — so a range that tight is claiming to know something nobody has measured. Finance signing off on it is exactly the sort of thing the audit picks up.",
            second="I read the {window} line back to her: the range against {supply} runs {reported_band}. The sheet has the recovery marker under the floor at {floor_muL}, and every value it could be gives a different share.",
            detail="{reported_band}",
        ),
        "band_undercovers": observation(
            first="Finance went back over the ranges your notebook prints for the other windows on this stack and said they do not hold. On more than one of them the recovery share the window settled at afterwards sits outside the range the report printed at the time, which is the thing the billing clause exists to stop.",
            second="They put the {window} line up first: the range against {supply} printed {reported_band}. Of the {windows_reviewed} windows they ran your notebook over, only {windows_held} came out with a range that stood up.",
            detail="{windows_held}",
        ),
        "band_degenerately_wide": observation(
            first="The range in your report is so wide the director cannot do anything with it. Finance say a range that broad tells them less than the number they had before, and they are back to asking whether the analyser was worth the money at all.",
            second="I checked the {window} width with Priya. The range against {supply} runs {reported_band}, and the sheet has thirteen slots on it and an analyser that repeats to a tenth of a unit.",
            detail="{reported_band}",
        ),
        "band_same_width_whatever_was_collected": observation(
            first="Priya ran your notebook twice on our own window: once against the round as Owen left it in January, with the whole of the agreement still in hand, and once against the same window with the plant room and the riser both read. The recovery range changes too little compared with what those records settle. We cannot justify spending the grant on rounds if the report barely reflects the information they add.",
            second="She put the two runs in front of me on {window}. The range against {supply} is {band_before} before those rounds and {reported_band} with both of them on. With {rounds_between} visits between the two, the widths do not narrow enough to follow what was collected.",
            detail="{band_before}",
        ),
        "band_widths_do_not_track_records": observation(
            first="Priya compared the recovery ranges from the other windows on the stack with what each window's own sheet and analyser readings leave open. Their relative widths do not follow the differences in those records, so finance will not treat them as ranges the windows actually carry.",
            second="She put two of the reports in front of me. On {first_window} the recovery range is {reported_band}; on {other_window} it is {other_band}. Across the {windows_reviewed} windows, those widths do not move with what each window collected.",
            detail="{other_band}",
        ),
        "band_wrong_on_another_window": observation(
            first="Finance took the ranges your notebook prints for the other windows on this stack into their quarterly review. Ours held up and one of the others did not: the range it prints there is not one that window's own sheet can carry. They will not sign a set of reports where the same file is careful on one month and not on another.",
            second="I went back and asked them which one. It is {other_window}, where your notebook prints {other_reading}, which is nothing like what that window has actually collected, and {other_windows} of the ones they ran it over came back that way.",
            detail="{other_reading}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "shares_invariant_to_signature_shift": {
        "figure_carried_over": observation(
            first="Priya ran your notebook over one of the later windows on the stack and it printed the same split it prints for January, to the last decimal. Those are different months with different weather and nobody thinks the supplies landed in the same place twice, so whatever the notebook is doing, it is not reading that window's sheet.",
            second="She showed me the two reports side by side. Both come back with the recovery share at {reported_share}, one for {window} and one for {other_window}.",
            detail="{other_window}",
        ),
        "shift_slope_from_header_rows": observation(
            first="Priya ran your notebook over the matching block next door and it comes back with a different split for the same month on the same main. The movement follows the pattern she gets when each block's header rows are allowed to stand in for the dosing rate, even though those rows move with the weather for their own reasons. The director cannot take a January split that changes when the block does.",
            second="She put the pair down for me. On {window} the {supply} share comes back at {reported_share} and on {other_window} at {other_share}, {moved_by} apart, on one main that feeds both.",
            detail="{moved_by}",
        ),
        "shares_track_shift_size": observation(
            first="Priya ran your notebook over the matching block next door, which takes the same three supplies off the same main, and the two do not agree. The mixture in that main is one mixture, so a split that moves when only the block's own makeup dosing moves is reading the dosing rather than the supplies.",
            second="She wrote the pair down for me. On {window} the {supply} share comes back at {reported_share} and on {other_window} at {other_share}, {moved_by} apart, on the same main in the same month.",
            detail="{moved_by}",
        ),
        "set_aside_rows_track_the_changeover": observation(
            first="Priya ran your notebook over the matching block whose changeover fell in the morning rather than the afternoon, and it comes back with a different split from ours for the same month on the same main. The movement follows one fixed part of the day rather than what each block's board says was actually connected.",
            second="She put the two next to each other for me. On {window} the {supply} share comes back at {reported_share} and on {other_window} at {other_share}, {moved_by} apart, and the only thing between the two blocks is the hour their changeover ran.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_visit_identifies_mixture": {
        "visit_is_not_a_call_or_a_stop": observation(
            first="Priya went to book the next visit off your notebook and it gave her nothing she could hand the desk. They take a point, a dwell and a number of slots, and short of that she needs to be told there is nothing left worth buying.",
            second="She showed me what came back for {window}: {reported}. The desk takes one point and a whole number of slots at five minutes or at thirty, and anything else it will not take at all.",
            detail="{reported}",
        ),
        "visit_infeasible": observation(
            first="Priya checked a visit your work called for against the analyser desk's terms. It is one the desk will not serve; sending it would still use that day's round and the agreement would charge the slots.",
            second="On {window}, the work called for {samples_asked} slots at {point}, {dwell_min} minutes each. Against the desk's terms, the result is: {reason}.",
            detail="{reason}",
        ),
        "visit_over_the_slots_left": observation(
            first="Priya tried to book the visit your notebook asked for and the desk bounced it: this window has nothing like that left of its grant and the slots do not roll over. She needs the notebook to know when the grant is gone.",
            second="The desk copied me on the bounce. On {window} the notebook asked for {samples_asked} slots at {point}, which comes to {slots_asked} against the {slots_left} the window has left.",
            detail="{slots_asked}",
        ),
        "visit_adds_no_identification": observation(
            first="Priya took the visit your notebook asked for into planning review before booking it. They cannot show that it materially narrows what remains unidentified, so she has held the slots rather than spend a grant that has few of them.",
            second="On {window} the notebook asked for {samples_asked} slots at {point} at {dwell_min} minutes. The recovery range currently printed is {recovery_band}, and planning review says that visit does not materially narrow the remaining identification problem.",
            detail="{recovery_band}",
        ),
        "stopped_with_slots_still_left": observation(
            first="Priya asked the notebook what to book next and it told her there was nothing worth booking, while the agreement still has slots on it and the desk still has days it will serve. Planning review can still find an affordable visit that materially narrows or completes the evidence behind the recovery answer, and once February's days are past nobody can buy them back.",
            second="She ran it again in front of me on {window} and it still says stop. There are {slots_left} slots left on the agreement; the recovery range on your own report, against the {asked_for} the director asked for, is {recovery_band}, and the ledger {rate_status}.",
            detail="{slots_left}",
        ),
        "visit_wrong_on_another_window": observation(
            first="Priya went round the other windows on the stack with your notebook before the planning meeting, asking each of them what to book next. Ours came back with something she could put to the desk and one of the others did not, and that window's owner has spent the afternoon asking me why energy management is handing him a visit he cannot make.",
            second="She named the window for me afterwards. It is {other_window}, where what your file hands the desk is {other_reading} and that window cannot act on it, and {other_windows} of the ones she ran the file over came back that way.",
            detail="{other_reading}",
        ),
        "candidate_execution_failed": observation(
            first="Priya ran your notebook across the planning states on the reporting stack, and one of the requests stopped before it returned a decision. She cannot take a batch of plans to the desk while the same notebook fails part way through it.",
            second="I watched her run the planning batch again. The failed run ended with {error}, and the batch still does not complete.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "ledger_unreadable": observation(
            first="The desk's billing review could not open the visit ledger that came with your report. Until they can, nothing the report says about what this window has spent stands up, and finance are treating the season's analyser spend as unaccounted for.",
            second="I forwarded the file to the desk and they sent back the line they stopped on: {reason}. That file is the desk's own record and the report has to reach the director with it intact.",
            detail="{reason}",
        ),
        "visits_are_not_a_ledger": observation(
            first="Finance opened your report looking for the line-by-line of what the analyser agreement has cost and found nothing they could read. They are holding the season's grant against the report until it is accounted for.",
            second="I looked myself before writing back. The visit list on the {window} report reads {reported}, and the ledger already carries {on_the_ledger} visits that somebody has to answer for.",
            detail="{on_the_ledger}",
        ),
        "visit_not_on_the_ledger": observation(
            first="The desk's billing review flagged a visit line that does not match any receipt as printed. Finance cannot reconcile a report if the call or its charged slots differ from the desk's own record.",
            second="They named the line for me: {call_id}, on the {window} report. The ledger carries {on_the_ledger} visits, and that line as printed does not match one of its receipts.",
            detail="{call_id}",
        ),
        "visit_details_disagree": observation(
            first="The desk found a visit line whose call id is theirs but whose sampling point is not what their receipt says. Finance cannot reconcile a charged round if the report moves it to another part of the system.",
            second="They named {call_id} on the {window} report. Your line says {reported_point}; the desk's receipt says {ledger_point}.",
            detail="{call_id}",
        ),
        "visit_counted_twice": observation(
            first="Finance caught the same visit charged twice inside your report. It is one round of the contractor's; counting it twice makes the season's spend look bigger than it is and the evidence behind the figures look broader than it is.",
            second="I counted the lines with them. {call_id} appears {times_reported} times on the {window} report and once on the desk's ledger.",
            detail="{call_id}",
        ),
        "refusal_uncounted": observation(
            first="Finance matched your report against the desk's bill and found a round we were charged for that the report never mentions. It is the one the desk handed back over the counter — nothing came of it, and it cost us the slots all the same. They want every slot this window has spent to appear, whether or not anything came back.",
            second="The desk put their own bill up beside the {window} report for me. Visit {call_id}, served on {served_on} at {point} for {slots_charged} slots, is on it and is not in your list.",
            detail="{call_id}",
        ),
        "receipt_missing": observation(
            first="Finance matched your report against the desk's bill and found visits we were charged for that the report never mentions. They want every slot this window has spent to appear in it, whoever booked it and whether or not it changed the figures.",
            second="The desk put their own bill up beside the {window} report for me. Visit {call_id}, served on {served_on} at {point} for {slots_charged} slots, is on it and is not in your list.",
            detail="{call_id}",
        ),
        "sample_counted_twice": observation(
            first="Priya read the slot account at the bottom of your report and found one slot listed twice. She cannot tell the director which slots stood behind the figures if a slot can appear in the account more than once.",
            second="She counted the lines with me on the {window} report. The identifier {sample_id} appears {times_reported} times in the account, although an identifier can occupy only one place there.",
            detail="{sample_id}",
        ),
        "sample_not_on_the_sheet": observation(
            first="Priya found a slot id in your account that is not on the sample sheet. A line the analyser never drew cannot stand behind the figures or be set aside from them.",
            second="She checked the {window} sheet again. It contains {on_the_sheet} slots inside the window, and {sample_id} is not one of them.",
            detail="{sample_id}",
        ),
        "sample_missing_from_the_account": observation(
            first="The director asked which slots on the sheet the figures actually stand on, and your report does not say. Every slot the analyser drew inside the window has to be in the account somewhere — behind the figures, or named as one that is not — because the ones that were left out are exactly what he will be asked about.",
            second="Priya went through the {window} sheet against your account with me. There are {on_the_sheet} slots on it inside the window, and {sample_id} is not in your account at all.",
            detail="{sample_id}",
        ),
        "sample_in_wrong_part_of_account": observation(
            first="Priya checked the two sample lists against the operations board and found a slot on the wrong side of the account. The report cannot say which slots stand behind the figures if its used and set-aside labels disagree with what the board says was connected to this header.",
            second="We checked {sample_id} on the {window} report. Your account puts it under {reported_part}; the board puts it under {expected_part}.",
            detail="{sample_id}",
        ),
        "account_wrong_on_another_window": observation(
            first="The desk's billing review ran your notebook across the whole stack when they reconciled the season's analyser bill. The line-by-line for our window matched what they charged and one of the others did not, so the season's spend is still open with finance and they are holding all of it, ours included.",
            second="I asked the desk which window it was. It is {other_window}, where {other_reading} in your report and what they charged do not line up, and {other_windows} of the ones they checked came back like that.",
            detail="{other_reading}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
