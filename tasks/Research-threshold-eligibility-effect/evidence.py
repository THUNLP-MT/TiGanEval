'The owner of the Northgate offer campaign, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ines Varga, growth operations lead. She works from the weekly readout, the council minute, "
    "the review desk's grant and whatever finance puts to her; the notebook's code, the offer "
    "register and the recompute log are not files she opens."
)

USER_BELIEF = """The standing-score offer has been running ten weeks on Northgate and the council wants a number on 9 June. My own read off the register is 33.6 percent of the accounts above the line ordering inside sixty days against 28.3 below it, so the offer is worth five points, and at five points it goes to every market on the slide.

Priya Raman runs the readout and is a long way ahead of me on the run and the export. If she tells me something about the scoring runs, the refresh batches or where the export stops, I take it as read; what any of it does to the number I could not tell you myself.

The review desk granted us 300 files. Two lots have gone already and one of those was refused and charged anyway, which I am still annoyed about. My own plan for the rest is to put them on the accounts that took the offer, because that is the side the council asks about every time.

Finance will ask how sure we are, and after the delivery-slot readout last quarter they will want every file this campaign has been charged for accounted for line by line.

How the register is built, and which accounts are actually in it, is not something I can answer. That is in the workspace, or in Priya's session notes."""

OBSERVATION_SCENE = "The 9 June pricing council readout"

_STOPPED_FIRST = (
    "Priya ran your notebook for the council pack and at least one required market readout did "
    "not come back. The pack is incomplete, so the council cannot use it."
)
_STOPPED_SECOND = (
    "I asked her to run {scope} again in front of me. The console ended with {error}, and that "
    "part of the council pack is still empty."
)

OBSERVATIONS = {
    "offer_effect_within_tolerance": {
        "uses_whole_book": observation(
            first="I took your readout to the council and finance stopped me on the first slide. Priya cannot reconcile the number with the signed at-the-line comparison in the council minute, and the readout does not show which rows produced it. Finance will not use a number whose population she cannot verify.",
            second="I reran the {market} readout with Priya. It prints {reported_points} points, which is {comparison_detail} from her signed reconstruction, and the report still gives her no row-level provenance for the disagreement.",
            detail="{reported_points}",
        ),
        "includes_carried_accounts": observation(
            first="Priya read your readout against the run notes and said its number matches the reading that includes accounts the run never scored. Those accounts got no offer, and the line did not pass them over — the run simply never reached them that week — and she says they order less than the book they were carried out of, so including them drags the side they land on.",
            second="We counted them on {market} this afternoon. The register carries {carried_rows} accounts the run carried rather than scored, out of {book_rows}, and your number matches the reading with them all included.",
            detail="{carried_rows}",
        ),
        "splits_on_register_score": observation(
            first="Priya pulled your readout apart and found that its number matches a split made from the standing score the register shows today. For a lot of accounts that is not the score their run read: the refresh batches landed after the offers went out and the register kept the new number. That split puts offered accounts on the passed-over side, and the other way round.",
            second="She showed me the count on {market}. There are {disagreeing_rows} accounts whose offer flag does not agree with the score against them today, and every one she checked is in the recompute log with a refresh dated after its own offer went out.",
            detail="{disagreeing_rows}",
        ),
        "keeps_credited_band": observation(
            first="Finance went through your readout with the account managers in the room and it did not survive. Its number matches a reading that keeps the accounts sitting in the first point above the line because a manager filed a credit for them, and managers file credits for accounts they are already courting. Treating those as accounts the line put over would count the manager's judgement as the offer's effect.",
            second="I had Priya count them off the register on {market}. There are {credited_rows} accounts standing over the line whose filed credit is what puts them there, and the ceiling on a credit here is {credit_ceiling}.",
            detail="{credited_rows}",
        ),
        "counts_orders_not_account_days": observation(
            first="Devin from data platform came back on your readout. Its number matches the count that treats an order against an account watched for sixty days like one watched for twenty, and the later runs were watched for nowhere near sixty. He says the two sides were not offered at the same time, so counting heads rather than time would not measure the same thing on both of them.",
            second="I put his note beside the {market} readout. The export stops on {export_stop_day}, orders reach it two days late, and the number the council is asking for is a {order_window_days}-day one.",
            detail="{export_stop_day}",
        ),
        "effect_disagrees": observation(
            first="Priya separately reconstructed the number from the campaign record and it does not agree with what your notebook prints. This is a disagreement between two readings of the available record, not a claim that the register cannot reproduce your calculation; the council is holding the item until we can sign one reading.",
            second="I sat with her over the {market} comparison. Your readout comes back at {reported_points} points against a line of {cut}; against her signed reconstruction the two results are {comparison_detail}.",
            detail="{reported_points}",
        ),
        "effect_wrong_on_another_market": observation(
            first="Priya ran your notebook over the other readouts required for the council's quarterly validation. Northgate reads back fine and one of the other cases does not: its number cannot be reconciled with that case's own campaign record. The council will not take a notebook that is right only on the window I happen to hold.",
            second="I asked her which case it was. It is {other_case}: {case_detail}. {other_markets} of the cases she ran came back wrong.",
            detail="{other_case}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_absent": observation(
            first="The council slide has a line under the number for how far it could still move and your readout does not fill it. Finance will not take a rate from us without one, not after the delivery-slot readout last quarter.",
            second="I opened the {market} readout again to copy the range across and the line reads {reported}. Finance wants a low and a high in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "effect_outside_range": observation(
            first="Finance cannot use the number and range together. The number the readout asks them to price does not sit between the range's two endpoints, so the slide gives two incompatible accounts of the same result.",
            second="I read the {market} lines back to them. The number is {reported_effect} points and the range is {reported_range}; the number is not inside it.",
            detail="{reported_range}",
        ),
        "account_days_absent": observation(
            first="Finance asked what the range in your readout stands on and there is nothing in it to answer them with. They want to see how much watching is behind the number before they sign anything that goes to seven markets.",
            second="I looked myself before writing back. The {market} readout prints a range of {reported_range} points and the line for what it stands on reads {reported}, so nobody can tell whether it is built on a fortnight of accounts or on ten weeks of them.",
            detail="{reported}",
        ),
        "account_days_disagree": observation(
            first="Priya reconciled the account-days printed below the range against the rows and review receipts. They do not add up, so finance cannot tell what evidence the range actually stands on.",
            second="For {market}, the readout prints {reported_account_days} account-days. The rows with the reviewed-file dates applied total {account_days_from_rows}, across {lots_charged} charged lots.",
            detail="{reported_account_days}",
        ),
        "range_below_floor": observation(
            first="Priya pushed back on the range in your readout. It is tighter than the account-days printed under it can carry, and finance's sentence is not about one window: the same notebook prints the slide for every market on it, so the range has to be one that would have been safe at any of them. She will not take this one to the council.",
            second="I read the {market} range back to her: {reported_range} points, on {reported_account_days} account-days. The slide carries {markets_on_the_slide} markets and this notebook produces every one of them.",
            detail="{reported_range}",
        ),
        "range_wider_than_the_evidence": observation(
            first="The range in your readout is so wide the council cannot do anything with it. It covers outcomes the accounts we have already watched rule out, and Priya says a range that ignores them makes the readout say less than we knew before it.",
            second="I checked the {market} width with her. The range runs {reported_range} points and it is standing on {reported_account_days} account-days, which cannot leave us that unsure.",
            detail="{reported_account_days}",
        ),
        "range_undercovers": observation(
            first="Finance went back over the readouts your notebook produces for the council's validation cases and said the ranges do not hold. On at least one of them the number that case settled at afterwards sits outside the range the readout printed, which is the exact thing the delivery-slot minute is about.",
            second="They put the {market} line up first: the range printed {reported_range} points. Of the {markets_reviewed} markets they ran your notebook over, only {markets_held} came out with a range that stood up.",
            detail="{markets_held}",
        ),
        "range_wrong_on_another_market": observation(
            first="Finance took the ranges your notebook prints for the other quarterly validation cases into their review. Northgate held up and one of the others did not: its number, range and the evidence printed beneath them do not make one account finance can sign. They will not sign a notebook that is careful only on the window I happen to hold.",
            second="I went back and asked them which case it was. It is {other_case}: {case_detail}. {other_markets} of the cases they ran came back wrong.",
            detail="{other_case}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "estimate_invariant_to_recompute_and_truncation": {
        "hardcoded_history": observation(
            first="Priya ran your notebook over one of the other markets on the slide and it printed the same number it prints for ours, to the last decimal. Those are different books on different windows and nobody thinks the offer landed in the same place on both, so whatever the notebook is doing, it is not reading that market's register.",
            second="She showed me the two readouts side by side. Both come back at {reported_points} points, one for {market} and one for {other_case}.",
            detail="{other_case}",
        ),
        "moves_with_recompute_batch": observation(
            first="Platform re-presented our Northgate window with the refresh batches drawn onto other days, which is something they do when they re-run a build, and your notebook's market-level number moved far enough that Priya cannot reconcile the two as readings of the same campaign. The rebuild changes a small minority of offer decisions, not the offer difference by anything like that much.",
            second="Priya put the pair in front of me. {market} comes back at {reported_points} points and {other_case} at {other_points}, {moved_by} points apart. The reissued build changes {changed_offer_rows} offer flags out of {book_rows} account rows.",
            detail="{moved_by}",
        ),
        "moves_with_export_stop": observation(
            first="Devin re-cut the Northgate export with the stop day moved, which he has to do when the extract job changes hands, and your notebook prints a materially different number off it. The offer flags and offer dates are unchanged; what changed is how long the export was left open.",
            second="He sent the two figures over. {market} comes back at {reported_points} points and {other_case} at {other_points}, {moved_by} points apart. The reissue keeps the offer flags and dates and changes the day the export stops.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_review_feasible_and_informative": {
        "review_grant_misspent": observation(
            first="While reconciling the review receipts, Priya found a booking made during this notebook's work that spent the campaign's grant without adding usable evidence: the desk refused it, returned too few files for a workable lot, returned files outside the readout's account set, or repeated accounts whose usable watching was already complete. That spend cannot be undone, even if the notebook now recommends a better next lot.",
            second="The receipt is {receipt_id} on {market}: {files_charged} files charged and {rows_returned} returned. The receipt review says {problem}.",
            detail="{receipt_id}",
        ),
        "review_is_not_a_lot_or_a_stop": observation(
            first="Priya exercised the notebook across the grant states the planning pack must survive and one answer gave her nothing she could act on. She has to hand the desk a run week, a band of points around the line, a share to pull from above it and a number of files, and short of that she needs a stop.",
            second="The failed state was {plan_state}. For {market} the notebook returned {reported}; that state has {files_left} files left.",
            detail="{reported}",
        ),
        "review_over_cap": observation(
            first="In Priya's grant-state rehearsal, one lot asked for more files than the desk works in one pass, so that planning state could not be booked.",
            second="The failed state was {plan_state}. On {market} the notebook asked for {files} files out of run week {week}, and the desk works {files_per_booking} in a booking.",
            detail="{files}",
        ),
        "review_one_side_of_the_cut": observation(
            first="In Priya's grant-state rehearsal, one lot put almost every file on one side of the line. The desk would refuse that state because a reviewer working only accounts that took the offer has nothing to compare them against.",
            second="The failed state was {plan_state}. On {market} the notebook asked for {above_share} of the lot from above the line, and the desk pulls between {above_share_low} and {above_share_high} from one side.",
            detail="{above_share}",
        ),
        "review_band_empty": observation(
            first="In Priya's grant-state rehearsal, one proposed band held files on only one side of the line in that week, so the desk could not work it as a comparison.",
            second="The failed state was {plan_state}. For {market} it asked for {files} files from run week {week} in a band of {band} points, but that band did not straddle the line.",
            detail="{band}",
        ),
        "review_over_grant": observation(
            first="In Priya's grant-state rehearsal, one proposed lot was larger than the files left in that state. The notebook has to remain usable as the grant is spent down.",
            second="The failed state was {plan_state}. On {market} the notebook asked for {files} files and that state has {files_left} left.",
            detail="{files_left}",
        ),
        "review_below_the_smallest_lot": observation(
            first="In Priya's grant-state rehearsal, one proposed lot was too small for a reviewer to open; the desk's set-up would cost more than the reading is worth.",
            second="The failed state was {plan_state}. On {market} the notebook asked for {files} files out of run week {week}; the desk minimum is {smallest_lot}, with {files_left} left in that state.",
            detail="{smallest_lot}",
        ),
        "review_outside_the_band": observation(
            first="In Priya's grant-state rehearsal, one proposed lot would spend files outside the account set the readout uses. Those files cannot change its number or range.",
            second="The failed state was {plan_state}. On {market} it asked for {files} files out of run week {week} at a band of {band} points, and {files_the_number_uses} returned files belong to the reading.",
            detail="{files_the_number_uses}",
        ),
        "review_adds_no_observation": observation(
            first="In Priya's grant-state rehearsal, one proposed lot would return accounts the readout already has all the usable watching for. It spends the grant without adding evidence to the number or range.",
            second="The failed state was {plan_state}. On {market} the proposed week-{week} lot adds {observation_days_gained} observed account-days even though it asks the desk for {files} files.",
            detail="{observation_days_gained}",
        ),
        "review_after_the_range_is_made": observation(
            first="In Priya's grant-state rehearsal, one case kept asking for files after its range was already tight enough for the council to act on. The minute says to stop buying at that point.",
            second="The failed state was {plan_state}. On {market}, where the council stops at {range_bar_points} points end to end, the notebook asked for {files} more files out of run week {week}.",
            detail="{range_bar_points}",
        ),
        "stopped_with_files_in_hand": observation(
            first="In Priya's grant-state rehearsal, one case stopped while that state could still fund a desk-sized lot and its range had not met the council's stopping condition.",
            second="The failed state was {plan_state}. On {market} it says stop with {files_left} files left, while the desk works lots down to {smallest_lot}.",
            detail="{files_left}",
        ),
        "review_wrong_on_another_market": observation(
            first="Priya ran the notebook over the other planning cases used before the council meeting. Northgate came back with a lot she could put to the desk and one of the others did not, so she cannot finish the grant plan from this notebook.",
            second="She named the case for me afterwards. It is {other_case}: {case_detail}. That case has {files_left} files left, and {other_markets} cases came back wrong.",
            detail="{other_case}",
        ),
        "review_elsewhere_after_the_range_is_made": observation(
            first="Priya ran the notebook over the other planning cases used before the council meeting. Northgate came back with a lot she could put to the desk. One of the other cases asks for more files even though its range is already tight enough for the council to act on, so the notebook is spending a grant after the minute says to stop.",
            second="She named the case for me afterwards. It is {other_case}: {case_detail}. The council stops there at {range_bar_points} points end to end, and {other_markets} cases came back wrong.",
            detail="{other_case}",
        ),
        "candidate_execution_failed": observation(
            first="Priya ran your notebook to work out what to book next and at least one required market did not return a booking answer. The planning pack is incomplete, so she cannot finish allocating the grant.",
            second="I watched her run {scope} again. The console ended with {error}, and the planning answer is still missing.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="The review desk could not open the receipt file that came with your readout. Until they can, nothing the readout says about what this campaign has spent stands up, and finance is treating the quarter's review spend as unaccounted for.",
            second="I forwarded the file to the desk and they sent back the line they stopped on: {reason}. The receipts are the desk's own record and the readout has to reach the council with them intact.",
            detail="{reason}",
        ),
        "lots_are_not_a_ledger": observation(
            first="Finance opened your readout looking for the line-by-line of what the review files have cost and found nothing they could read. They are holding the rest of the grant against the readout until it is accounted for.",
            second="I looked myself before writing back. The lot list on the {market} readout reads {reported}, and the desk has already charged us for {charged} lots that somebody has to answer for.",
            detail="{charged}",
        ),
        "receipt_missing": observation(
            first="Finance matched your readout against the review desk's bill and found lots we were charged for that the readout never mentions. They want every file this campaign has spent to appear in it, whoever booked it and whether or not it changed the answer.",
            second="I pulled the receipts up beside the {market} readout. Lot {receipt_id}, charged {files_charged} files, is on the bill and is not in the list.",
            detail="{receipt_id}",
        ),
        "refusal_uncounted": observation(
            first="Finance found a lot on the desk's bill that your readout leaves out, and it is one of the refused ones. A refusal costs us the files exactly as a worked lot does — that is the whole reason I am cross about March — so leaving it out of the accounting makes the grant look bigger than it is.",
            second="I put the bill beside the {market} readout. Lot {receipt_id} was refused and charged {files_charged} files, and the readout lists everything except it.",
            detail="{receipt_id}",
        ),
        "lot_not_on_the_receipts": observation(
            first="The review desk flagged a line in your readout they have no record of. A lot the desk never worked, or one with numbers against it that are not what they charged, cannot sit in a readout the council acts on.",
            second="They named the line for me: {receipt_id}, on the {market} readout. The desk carries {charged} lots for this campaign and that is not one of them as it is written.",
            detail="{receipt_id}",
        ),
        "lot_counted_twice": observation(
            first="Finance caught the same lot billed twice inside your readout. It is one morning of one reviewer; counting it twice makes the campaign's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {receipt_id} appears {times_reported} times on the {market} readout and once on the desk's receipts.",
            detail="{receipt_id}",
        ),
        "receipts_wrong_on_another_market": observation(
            first="The review desk ran your notebook across the quarterly validation cases when they reconciled this quarter's bill. The line-by-line for Northgate matched what they charged and one of the other cases did not, so the quarter's review spend is still open with finance and they are holding all of it, ours included.",
            second="I asked the desk which case it was. It is {other_case}: {case_detail}. {other_markets} of the cases they checked came back wrong.",
            detail="{other_case}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
