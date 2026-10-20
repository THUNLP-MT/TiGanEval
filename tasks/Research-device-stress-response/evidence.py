'The owner of the QR-40 submission, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ruth Halloran, submission owner for the QR-40 coupling family. She works from the run "
    "table, the bench sheet, the chamber bill and whatever the reviewer puts to her; the "
    "notebook's code and the receipt stream are not files she opens."
)

USER_BELIEF = """The March ladder for QR-40 is finished and the submission is due on the 19th. It needs one pressure out of the ladder: where one in ten of the family leak. My own file gives 168.9 bar, which is where the line through the six cartridges reaches one in ten, and that is twenty-one bar under the rating we quoted the customer. If the family really sits there we cannot sign what they were told.

Sanne Devries ran the batches and is a long way ahead of me on the benches and the consoles. If she tells me something about a bench, a console sticker or a hold I take it as read, and what any of it does to the number I could not tell you myself.

Nine chamber hours are left on this review before the submission closes, and the stores hold thirty-four couplings. My own plan for the hours is C-300, because that is the cartridge the leaks are at.

The reviewer will ask how far the number could still move, and the chamber desk bills us for every hour whether the sheet runs or not, so finance want each of those hours in the report.

How the run table is built, and which of its rows carry a pressure at all, is not something I can answer. That is in the workspace, or in Sanne's notes."""

OBSERVATION_SCENE = "The QR-40 submission review"

_STOPPED_FIRST = (
    "One of the qualification report runs stopped before its report was complete. The review "
    "cannot rely on a notebook that stops on one of the records the review runs it over."
)
_STOPPED_SECOND = (
    "I asked Sanne to run the failing case again in front of me. The console ended with "
    "{error}, and that report still did not complete."
)

OBSERVATIONS = {
    "crossing_within_tolerance": {
        "crossing_in_console_bar": observation(
            first="I took your number to the reviewer and Sanne stopped me before the first slide. She says it is worked out of the figures the consoles wrote and not out of pressure, and that the two benches do not write the same figure for the same cartridge. The reviewer will not take a rating built on one console's arithmetic and the other's.",
            second="I sat down with the {lot} bench sheet afterwards. The dead-weight block is certified at {block_bar} bar and {bench} wrote {block_reading_bar} for it on {batch}, and your number is worked out of that bench's figures as they stand.",
            detail="{block_reading_bar}",
        ),
        "crossing_uses_the_pinned_rows": observation(
            first="Sanne read your number against the run table and said the top of the ladder is not where your file is putting it. Those cartridges never came back with a pressure at all, so whatever the number is standing on up there, it is not what the chamber did to the couplings.",
            second="I went back through the {lot} table with her. {pinned_units} rows came back sitting on the sticker figure of {span_bar} bar, {cartridge} among them, and your number counts them as though the sticker were the pressure.",
            detail="{pinned_units}",
        ),
        "crossing_pools_the_short_hold": observation(
            first="The reviewer asked why our number does not agree with the ladder run at the plan's hold, and Sanne found your file pouring one batch in with the rest. That batch was not run the way the plan is written, and the submission is a statement about the plan's own hold.",
            second="We put the {lot} table up beside the plan. The plan is written against {plan_hold_min} minutes, {batch} ran at {short_hold_min}, and your number folds all {short_hold_units} of those couplings into the same ladder as the plan-hold rows.",
            detail="{short_hold_units}",
        ),
        "crossing_disagrees": observation(
            first="Sanne rebuilt the number off the run table this afternoon and could not land anywhere near what your notebook gives. The reviewer is holding the submission until the report and the table tell one story.",
            second="I sat with her and we went through the {lot} ladder line by line. Your report comes back at {reported_bar} bar for the family at the plan's {plan_hold_min} minutes, and neither of us can get the table to give that.",
            detail="{reported_bar}",
        ),
        "crossing_wrong_on_another_lot": observation(
            first="Sanne ran your notebook over the other lots reliability uses it for while she was preparing the next reviews. Ours reads back, but at least one other lot's pressure line cannot be supported from that lot's own records. The reviewer will not take a shared reporting file while it still returns an unsupported line on a lot it is meant to serve.",
            second="I asked her to read the result back rather than diagnose it for me. The first failed result she read back is from {other_lot}, where the pressure field says {reported_bar}. The check failed on {other_lots} different lots in all; that number is the count that failed, not the count she ran.",
            detail="{reported_bar}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_a_pair": observation(
            first="The reviewer cannot read the range line under the pressure as a low value followed by a high value. A range that cannot be read in that order cannot go into the submission, not on a family this size.",
            second="I opened the {lot} report again to copy the range across and the line reads {reported}. The reviewer wants a low and a high in that order with the pressure sitting between them.",
            detail="{reported}",
        ),
        "range_does_not_contain_reported_crossing": observation(
            first="The reviewer cannot reconcile the pressure in your report with the range printed under it. The pressure itself sits outside that range, so the two lines cannot both describe the same result.",
            second="I put the two lines from the {lot} report beside each other. The pressure is {reported_bar} bar and the range underneath it is {reported_range}.",
            detail="{reported_range}",
        ),
        "range_not_centred_on_reported_crossing": observation(
            first="The two sides of the range are not the same distance from the pressure printed above them. The reviewer cannot treat that as one uncertainty placed around the same fitted number.",
            second="I put the two lines from the {lot} report beside each other. The pressure is {reported_bar} bar and the range is {reported_range}; its two sides are not balanced around that pressure.",
            detail="{reported_range}",
        ),
        "range_narrower_than_the_units_support": observation(
            first="Sanne pushed back on the range in your report. She says it is tighter than this ladder can carry — the couplings behind it do not settle the number that closely — and a range that tight is a claim the submission cannot stand behind if anything comes back from the field.",
            second="I checked the width with her against the table. The {lot} range runs {reported_range}, and she says the couplings this ladder stands on will not hold the number inside a band that narrow.",
            detail="{reported_range}",
        ),
        "range_wider_than_the_units_support": observation(
            first="The range in your report is so wide the reviewer cannot do anything with it. It covers pressures the couplings we already ran rule out, and Sanne says a range that ignores them makes the report say less than the ladder knew before it.",
            second="I read the {lot} width back to her: {reported_range}. She says the couplings the qualification put on that ladder rule out a good part of what that width still leaves open.",
            detail="{reported_range}",
        ),
        "range_wrong_on_another_lot": observation(
            first="The reviewer took the ranges your notebook prints for the other lots reliability uses it for into the quarterly file. Ours passed review and at least one of the others did not: its range line cannot be accepted against that lot's own report and records.",
            second="I went back and asked her to read the line itself to me. It is {other_lot}, where your notebook prints {reported_range}; {other_lots} of the lots they put it over came back with a range line that did not stand up to review.",
            detail="{reported_range}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "crossing_invariant_to_bench_calibration": {
        "crossing_missing_on_live_lot": observation(
            first="The audit can read a pressure from a second reading of the March couplings, but the March report itself leaves the pressure blank. With only one side of that comparison, the reviewer cannot establish that the family number stays put when only the bench record changes.",
            second="I asked Sanne to put the two reports beside each other. The {lot} report says {reported} where the pressure should be, while the audit's {other_lot} reading returns {other_bar} bar.",
            detail="{other_bar}",
        ),
        "crossing_missing_on_redraw": observation(
            first="The audit ran the notebook over a second reading of the same March couplings with only the bench records redrawn, and the notebook left the pressure blank. Without a number from both readings, they cannot tell whether the reported family pressure stays put when the bench record changes.",
            second="I asked Sanne to show me the pair. The report for {other_lot} says {reported} where the pressure should be, so there is no second number to compare with {lot}.",
            detail="{reported}",
        ),
        "crossing_carried_over_from_this_lot": observation(
            first="Sanne ran your notebook over one of the lots queued behind ours and it printed the same pressure it prints for March, to the last decimal. Those are two different families on two different ladders and nobody thinks they landed in the same place, so whatever the notebook is doing, it is not reading that lot's table.",
            second="She showed me the two reports side by side. Both come back at {reported_bar} bar, one for {lot} and one for {other_lot}.",
            detail="{other_lot}",
        ),
        "crossing_tracks_the_bench_scale": observation(
            first="Metrology recalibrated both benches and Sanne re-ran your notebook over the March table on the new certificates. It came back at a different pressure. Nothing was done to a single coupling between those two runs, so a number that moves when only the certificates move is reading the benches.",
            second="She wrote the pair down for me. {lot} comes back at {reported_bar} bar and {other_lot} at {other_bar}, {moved_by} bar apart, on the same couplings.",
            detail="{moved_by}",
        ),
        "crossing_tracks_which_bench_a_batch_ran_on": observation(
            first="The audit re-ran the March ladder the way it would have gone if the bays had been free the other way round — the same batches, the same couplings, the same holds, put on the other bench. Your notebook comes back at a different pressure for it. Which bay happened to be free in March is not a fact about the family.",
            second="They sent me the two numbers. {lot} comes back at {reported_bar} bar and {other_lot} at {other_bar}, {moved_by} bar apart, and the only thing between them is which bench took which batch.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_block_reaches_the_crossing": {
        "charged_session_did_not_advance_the_crossing": observation(
            first="The chamber bill now contains a session booked after this handoff that did not put a usable full set of couplings at the pair of levels around the crossing. That time is already gone, so a later instruction to stop cannot make the booking useful to this review.",
            second="I traced it to receipt {booking_id}: it charged {hours_charged} hours for {units_returned} couplings returned at {cartridge} for {dwell_min} minutes. Sanne's check says that session did not buy a usable full set at the two levels around the crossing.",
            detail="{booking_id}",
        ),
        "block_is_not_a_session_or_a_stop": observation(
            first="Sanne went to book the next chamber session off your notebook and it gave her nothing she could put in front of the desk. She has to hand them a bench, a batch, a cartridge, a hold and a number of couplings, and short of that she needs to be told there is nothing left worth booking.",
            second="She showed me what came back for {lot}: {reported}. The desk takes one sheet with those five things on it and nothing else at all.",
            detail="{reported}",
        ),
        "block_books_a_bench_or_batch_it_cannot": observation(
            first="Sanne checked the next session from your notebook against the chamber desk's records and could not clear it for booking. Something the session names is not available to that review, so there is no usable next sheet yet.",
            second="She read the proposed sheet back to me. On {lot} the notebook asks for {units} couplings of {batch} at {cartridge} on {bench}; the next day recorded for that review is {served_on}, and the proposal does not line up with the desk's availability records.",
            detail="{served_on}",
        ),
        "block_over_the_hours_or_ports": observation(
            first="Sanne checked the proposed session against the capacity left in that review. It asks for more chamber capacity than the review has at that point, so it cannot be used as the next booking.",
            second="She read the numbers from the {lot} proposal back to me. It asks for {units} couplings in a {hours_charged}-hour session; the chamber has {ports} ports and the review has {hours_left} hours left.",
            detail="{hours_charged}",
        ),
        "block_at_the_wrong_hold": observation(
            first="Sanne checked the session your notebook proposes and found that its hold is not the one the submission is written against. Booking it would spend chamber time on a different question about the family.",
            second="She showed me the proposed sheet for {lot}. The notebook asks for {dwell_min} minutes and the plan the submission is written against is {plan_hold_min}.",
            detail="{dwell_min}",
        ),
        "block_at_a_cartridge_the_gauge_cannot_read": observation(
            first="Sanne checked the cartridge in the proposed session against the console record. Every coupling there would stop at the sticker figure, so the booking would buy no pressure level for the ladder.",
            second="She read the proposal and the {lot} bench record back to me. The notebook sends her to {cartridge}, and the sticker on the front of the console is {span_bar} bar, where that cartridge's readings stop.",
            detail="{cartridge}",
        ),
        "block_does_not_reach_the_crossing": observation(
            first="Sanne checked where the proposed session sits on the current ladder. It puts the next couplings in a part the ladder has already settled instead of at the two levels around the crossing, so it does not spend the next chamber session on the decision still open.",
            second="She sent me the proposed sheet. On {lot} the notebook asks for {units} couplings at {cartridge}, while stores have {stores_left} of {batch} standing.",
            detail="{cartridge}",
        ),
        "block_leaves_the_ports_empty": observation(
            first="The proposed session leaves fillable chamber capacity unused even though its batch can supply more couplings. A plan-hold session has a fixed chamber cost, so the review would buy less evidence than the available ports and stock allow.",
            second="Sanne sent me the proposed sheet. On {lot} the notebook asks for {units} couplings at {cartridge}, the chamber holds {ports} ports and stores have {stores_left} of {batch} standing.",
            detail="{units}",
        ),
        "stopped_with_hours_left": observation(
            first="Sanne asked the notebook what to book next and it told her there was nothing worth booking, while the review still has hours on it and the stores still have couplings. If we hand those hours back now the submission goes in on the ladder as it stands and we cannot get the chamber time again before the 19th.",
            second="She ran it again in front of me on {lot} and it still says stop. There are {hours_left} chamber hours left and {stores_left} couplings standing in stores.",
            detail="{hours_left}",
        ),
        "block_wrong_on_another_lot": observation(
            first="Sanne asked this notebook for the next decision on the other lots reliability uses it for. Ours returns a usable next step, but at least one other review does not get an action it can use against its own chamber state.",
            second="She read one of the answers back to me. On {other_lot}, with {hours_left} hours left, your notebook returns {reported_plan}; {other_lots} of the lots she checked did not get a next decision they could use.",
            detail="{reported_plan}",
        ),
        "candidate_execution_failed": observation(
            first="One of the planning runs stopped before the notebook returned a usable next decision. That review cannot decide what to do with its remaining chamber state.",
            second="I watched Sanne run the failing planning case again. The console ended with {error}, and that case still has no next decision.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="The chamber desk's billing review could not open the receipt stream that came with your report. Until they can, nothing the report says about what this review has spent stands up, and finance are treating the quarter's chamber time as unaccounted for.",
            second="I forwarded the file to the desk and they sent back the line they stopped on: {reason}. The stream is the desk's own record and the report has to reach the reviewer with it intact.",
            detail="{reason}",
        ),
        "sessions_are_not_a_ledger": observation(
            first="Finance opened your report looking for the hour-by-hour of what this review has cost the chamber and found nothing they could read. They are holding the rest of the grant against the report until it is accounted for.",
            second="I looked myself before writing back. The session list on the {lot} report reads {reported}, and the desk has already charged us for {charged} of them.",
            detail="{reported}",
        ),
        "hour_reported_twice": observation(
            first="Finance caught the same chamber session listed twice inside your report. Counting one charge twice makes the review's recorded spend and session count larger than the desk's stream.",
            second="I counted the lines with them. {booking_id} appears {times_reported} times on the {lot} report and once on the desk's stream.",
            detail="{booking_id}",
        ),
        "session_not_on_the_receipts": observation(
            first="The chamber desk's billing review flagged a line in your report they have no record of. A session the desk never served, or one whose numbers are not the ones they billed, cannot sit in a report the reviewer signs against.",
            second="They named the line for me: {booking_id}, on the {lot} report. The desk has charged this review for {charged} sessions and that line does not match any of them.",
            detail="{booking_id}",
        ),
        "handed_back_session_left_out": observation(
            first="Finance matched your report against the chamber bill and found a charge the report never mentions. The sheet came back over the counter and nothing ran on it, and they say that is exactly the kind of charged session a submission has to show rather than quietly drop.",
            second="I pulled the stream up beside the {lot} report. Session {booking_id}, served on {served_on} at {hours_charged} of an hour, is on the bill and is not in the list.",
            detail="{booking_id}",
        ),
        "charged_hour_missing": observation(
            first="Finance matched your report against the chamber bill and found a session we were charged for that the report never mentions. They want every hour this review has spent to appear in it, whoever booked it and whether or not it changed the number.",
            second="I pulled the stream up beside the {lot} report. Session {booking_id}, served on {served_on} at {hours_charged} of an hour, is on the bill and is not in the list.",
            detail="{booking_id}",
        ),
        "counted_units_carry_no_source": observation(
            first="The reviewer could not read a complete provenance count from your report. Each entry needs its source and non-negative whole unit and leak counts before the accounting can be reconciled.",
            second="I checked the {lot} provenance line again: {issue}. Each entry needs non-negative whole units and leaks no greater than its units; the source words the reporting tooling accepts are {sources}.",
            detail="{issue}",
        ),
        "block_check_counted_as_a_unit": observation(
            first="Sanne compared the batch-table coupling count with the ladder and found that the excess is exactly the number of block-check rows. The block goes on the bench at the start and end of a batch as an equipment check; it is not coupling stock.",
            second="We counted the {lot} report and table together. Your report claims {reported_units} batch-table couplings, and the table contains {block_checks} rows for the block itself in addition to its coupling rows.",
            detail="{block_checks}",
        ),
        "counted_units_disagree": observation(
            first="Finance could not reconcile one provenance count in your report with its underlying source records. They will not sign a submission where the number and the stated units and leaks behind it tell different stories.",
            second="I went through the {lot} line with them. Your report claims {reported_units} units with {reported_leaks} marked as leaks from {source}, and the source records do not reproduce that pair.",
            detail="{reported_leaks}",
        ),
        "report_wrong_on_another_lot": observation(
            first="Finance ran the notebook across the other lots reliability uses it for. Our report reconciles, but at least one other lot's accounting does not line up with that lot's source records, so the shared reporting file is not ready for the quarterly review.",
            second="I asked finance to read back the line they stopped on. It is {other_lot}, and the detail from that report is {reported_accounting}; {other_lots} of the lots they checked did not reconcile to their source records.",
            detail="{reported_accounting}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
