'The owner of the EM-9 March review, and what he reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Anders Kolbe, reliability lead on the EM-9 emitter family. He works from the trace "
    "export, the incoming sheet, the decay catalogue, the chamber bill and whatever the "
    "reviewer puts to him; the notebook's code and the receipt stream are not files he opens."
)

USER_BELIEF = """The March soak on EM-9 closed on the 24th and the review sits on the 26th. It needs one number out of the export: the hours before a module loses a tenth of its output at the drive and case we specify. My own file gives 4,509, which is where loss against log hours reaches a tenth, and that clears the 3,000 hours on the datasheet by half again. Nobody on the bench believes this family is that good, and I cannot put my name to a number the bench will not stand behind.

Nils Aaberg ran both racks and is a long way ahead of me on the racks, the loggers and the bench meter. If he tells me something about a logger profile, a sticker or a reference read I take it as read, and what any of it does to the number I could not tell you myself. Two things I have seen for myself: every trace opens flat on the same figure whatever module it is, and L-14 comes back slower than L-11 whatever I plot, which is the lot that went on R-B.

Fourteen chamber-days are left on this review before it sits, and the shop holds twelve spare modules. My own plan for the days is more ports at 1.7 A, because that is the drive the loss actually shows at.

The reviewer will ask how far the number could still move, and the chamber desk bills us for every day whether the block runs or not, so finance want each of those days in the report.

Which laws in the catalogue this build is still allowed to be is the argument reliability has been having since the family opened, and it is not one I can settle from my desk."""

OBSERVATION_SCENE = "The EM-9 March soak review"

_STOPPED_FIRST = (
    "Nils opened your notebook to print the number for the review pack and the run stopped "
    "before anything came out. There is a blank where the hours go."
)
_STOPPED_SECOND = (
    "I asked him to run it again in front of me. The console ended with {error}, and the page "
    "is still blank."
)

OBSERVATIONS = {
    "hours_to_loss_within_tolerance": {
        "hours_read_off_the_pinned_start": observation(
            first="I took your number to the reviewer and Nils stopped me before the first slide. He can reproduce it by taking the row each module opened at as its start, and every trace opens on the same figure whatever module it is. The reviewer will not take a life number that coincides with a reading whose starting point is the same for a part that came in bright and a part that came in dull.",
            second="I sat down with the {campaign} export and the incoming sheet afterwards. {sticker_rows} module rows in it read {full_scale_mw} and nothing else, {module_id} among them, and the incoming sheet has that one at {incoming_mw} mW.",
            detail="{sticker_rows}",
        ),
        "hours_read_off_the_rows_on_the_sticker": observation(
            first="I took your number to the reviewer and Nils stopped me again. He can reproduce it by keeping every row in the export, including the rows on the meter's sticker. A row on that sticker only says the module was at least that bright, because the bench meter does not read above it, so the bench will not stand behind a life number that coincides with that reading.",
            second="We went back through the {campaign} export together afterwards. {sticker_rows} module rows in it read {full_scale_mw} and nothing else, {module_id} among them, and the incoming sheet has that one at {incoming_mw} mW; when Nils keeps those rows, his result lands alongside the {reported_hours} hours your report prints.",
            detail="{sticker_rows}",
        ),
        "hours_read_off_the_elapsed_hours_column": observation(
            first="Nils read your number against the export and can reproduce it by treating the elapsed column as hours. One rack's column and the other rack's column do not mean the same thing, and the stamps say so. The reviewer is not going to sign a life number that coincides with a reading whose axis depends on which bay a module happened to go in.",
            second="He put the two side by side for me on {campaign}. {module_id} on {rack} is at {column_hours} in the elapsed column and its own stamps span {stamp_hours} hours; treating the column as hours lands alongside the {reported_hours} hours your report prints.",
            detail="{column_hours}",
        ),
        "hours_disagrees": observation(
            first="Nils rebuilt the number off the export this afternoon and could not land anywhere near what your notebook gives. The reviewer is holding the sign-off until the report and the export tell one story.",
            second="I sat with him and we went through the {campaign} rows line by line. Your report comes back at {reported_hours} hours for the family at {field_drive_a} A and {hold_temp_c} C, and neither of us can get the export to give that.",
            detail="{reported_hours}",
        ),
        "hours_absent": observation(
            first="Nils opened the report for the review and there is no usable tenth-loss number on the page. The reviewer cannot sign the family off without a numeric result from the export.",
            second="I sat with him and opened the {campaign} report again. At {field_drive_a} A and {hold_temp_c} C, the hours entry reads {reported_hours} rather than a number the review can use.",
            detail="{reported_hours}",
        ),
        "hours_wrong_on_another_campaign": observation(
            first="Nils ran your notebook over the other campaigns reliability runs it over, while he was setting the rig up for the ones that come next. Ours reads back fine and one of the others does not: the team that owns it does not recognise the life your file prints for their build, and they have been soaking that family since the spring. The reviewer will not take a report from a file that hands two teams numbers which cannot both be right.",
            second="I asked him which one it was. It is {other_campaign}, and {other_campaigns} of the ones he ran the same file over came back with a life their own export does not have.",
            detail="{other_campaign}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_spans_the_standing_laws": {
        "range_is_not_a_pair": observation(
            first="The review page has a line under the number for how far it could move and your report does not fill it. The reviewer will not take a life figure from us without one, not on a family this size.",
            second="I opened the {campaign} report again to copy the range across and the line reads {reported}. The reviewer wants a numeric low and high in that order.",
            detail="{reported}",
        ),
        "range_does_not_hold_reported_hours": observation(
            first="The reviewer pointed at the life number and the range printed under it: the number is outside its own range. A range cannot say how far that figure may move if it does not hold the figure it qualifies.",
            second="I opened the {campaign} report with them. It prints {reported_hours} hours and puts {reported_range} underneath it, so the low and high do not bracket the number above.",
            detail="{reported_range}",
        ),
        "range_narrower_than_the_laws_leave": observation(
            first="Nils pushed back on the range in your report. It is tighter than the signed-off evidence rule allows: the review treats the full gap between standing-law answers as a half-width and also checks the three-standard-error floor from the counted rows, then uses whichever is larger.",
            second="I checked the {campaign} width with him against its {counted_rows} counted rows. The report prints {reported_range}, a half-width of {reported_half_width}; the evidence rule requires at least {required_half_width}.",
            detail="{required_half_width}",
        ),
        "range_wider_than_the_laws_leave": observation(
            first="The range in your report is so wide the reviewer cannot do anything with it. It covers lives the modules we already soaked rule out, and Nils says a range that ignores them makes the report say less than the export knew before it.",
            second="I read the {campaign} width back to him: {reported_range}, off {counted_rows} rows. He says the rows this campaign actually ran rule out a good part of what that width still leaves open.",
            detail="{reported_range}",
        ),
        "range_misses_the_hours": observation(
            first="The reviewer went back over the reports your notebook produces for the other campaigns reliability runs it over and said the ranges do not hold. On more than one of them the life that build settled at afterwards sits outside the range the report printed at the time, which is the exact thing the range is written for.",
            second="They put the {campaign} line up first: the range printed {reported_range}. Of the {campaigns_reviewed} campaigns they ran your notebook over, only {campaigns_held} came out with a range that stood up.",
            detail="{campaigns_held}",
        ),
        "range_wrong_on_another_campaign": observation(
            first="The reviewer took the ranges your notebook prints for the other campaigns reliability runs it over into the quarterly file. Ours held up and one of the others did not: the width it prints there is not one that export can carry. They will not sign a set of reports where the same file is careful on one campaign and not on another.",
            second="I went back and asked which one. It is {other_campaign}, where the range the notebook prints is nothing like what that campaign actually ran, and {other_campaigns} of the ones they put it over came back that way.",
            detail="{other_campaign}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "hours_invariant_to_logger_cadence": {
        "hours_carried_over_from_this_campaign": observation(
            first="Nils ran your notebook over one of the campaigns queued behind ours and it printed the same life it prints for March, to the last decimal. Those are two different builds on two different racks and nobody thinks they landed in the same place, so the report is not distinguishing the two campaigns' evidence.",
            second="He showed me the two reports side by side. Both come back at {reported_hours} hours, one for {campaign} and one for {other_campaign}.",
            detail="{other_campaign}",
        ),
        "hours_track_the_elapsed_hours_column": observation(
            first="The bay re-issued the March export with the rebuilt logger's profile put back the way it had been running before the workshop, and Nils re-ran your notebook over it. It came back at a different life. Not one module was touched between those two runs, so a number that moves when only a logger profile moves is reading the logger.",
            second="He wrote the pair down for me. {campaign} comes back at {reported_hours} hours and {other_campaign} at {other_hours}, {moved_by} hours apart, on the same modules.",
            detail="{moved_by}",
        ),
        "hours_track_which_rack_was_rebuilt": observation(
            first="The audit re-issued the March export the way it would have gone if the workshop had taken the other rack's logger — the same modules, the same drives, the same stamps, the rebuild on the other bay. Your notebook comes back at a different life for it. Which logger happened to be in the workshop in January is not a fact about the family.",
            second="They sent me the two numbers. {campaign} comes back at {reported_hours} hours and {other_campaign} at {other_hours}, {moved_by} hours apart, and the only thing between them is which rack was rebuilt.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_block_parts_the_standing_laws": {
        "block_is_not_a_block_or_a_stop": observation(
            first="Nils went to book the next chamber block off your notebook and it gave him nothing he could put in front of the desk. He has to hand them a drive, a case temperature, a number of ports, a number of days and a lot, and short of that he needs to be told there is nothing left worth booking.",
            second="He showed me what came back for {campaign}: {reported}. The desk takes one sheet with those five things on it and nothing else at all.",
            detail="{reported}",
        ),
        "block_names_one_law": observation(
            first="Nils read the report your notebook writes before he booked anything and stopped. It names one law and books the days as though the argument about this family were settled. He says the export has not settled it, and that a block booked on one law buys nothing the review can use.",
            second="I went through the {campaign} report with him. It names {laws_named} law, {named_law}, and the catalogue's others are not accounted for anywhere in it.",
            detail="{named_law}",
        ),
        "block_names_a_law_the_rows_reject": observation(
            first="Nils could not reconcile the standing-law entry in your report with the catalogue and the campaign's export. He will not take a booking until the report gives him a readable list of catalogue laws that the rows still leave standing.",
            second="On {campaign}, the entry resolves to {laws_named} usable name or names; the first thing Nils can read from it is {named_law}. That entry does not reconcile with the catalogue and the rows he plotted.",
            detail="{named_law}",
        ),
        "block_infeasible": observation(
            first="Nils took the sheet your notebook asked for to the chamber desk and it came back over the counter. He lost the morning and the days were charged anyway, which is days out of the few we have before the review.",
            second="He sent me the counter slip. On {campaign} the desk wrote: {refusal}. That was for the day the schedule holds next, {served_on}.",
            detail="{refusal}",
        ),
        "block_at_a_setting_that_parts_nothing": observation(
            first="Nils compared the proposed sheet with the two catalogue laws still in the argument and stopped before booking it. At that setting they predict the same readings, so the block would spend days without deciding anything the review still has open.",
            second="He read the {campaign} sheet back to me: {drive_a} A at {case_temp_c} C for {chamber_days} days. Against the two laws the report still has standing, its predicted separation is {separation_share} of the strongest sheet still available.",
            detail="{separation_share}",
        ),
        "block_parts_too_little": observation(
            first="Nils compared the proposed sheet with the other blocks the desk can still serve. It would separate the two laws a little, but another available sheet opens much more of the argument for the same scarce chamber time, so the desk will not spend the days on this one.",
            second="He checked the {campaign} sheet at {drive_a} A and {case_temp_c} C. It opens {separation_share} as much ground as the strongest block still available; the desk's minimum is {required_share}.",
            detail="{separation_share}",
        ),
        "block_leaves_the_ports_empty": observation(
            first="Nils ran the block your notebook asked for and came back out of the bay with the rig half empty. The days are charged whatever is in it, so a sheet that leaves ports standing spends the same days for less than half the rows, and we have very few days.",
            second="He sent me the sheet. On {campaign} the notebook asked for {ports} ports and the shop could have filled {ports_free} out of {lot}.",
            detail="{ports}",
        ),
        "stopped_with_days_left": observation(
            first="Nils asked the notebook what to book next and it told him there was nothing worth booking, while the review still has days on it and the shop still holds spares. If we hand those days back now the review goes in on the export as it stands, and we cannot get the chamber again before the 26th.",
            second="He ran it again in front of me on {campaign} and it still says stop. There are {days_left} chamber-days left and {spares_left} spare modules standing in the shop.",
            detail="{days_left}",
        ),
        "block_booked_with_nothing_the_desk_will_take": observation(
            first="Nils took the sheet your notebook asked for down to the chamber desk and walked back out with it. Under the remaining days, stock and service schedule, the desk had no block it could serve, so nothing went in the rig and the morning went. He is planning the campaigns behind this one around whatever we hand back, and he needs the notebook to tell him when the chamber is finished with the March review rather than sending him down there for nothing.",
            second="He showed me the slip on {campaign}. It records the next served date as {served_on}, the rig's service window as {rig_out_of_service}, and the review at {days_left} chamber-days with {spares_left} spare modules. Your file asked him for {ports} ports of {lot} at {drive_a} A for {chamber_days} days all the same; taken together, the desk could not serve it.",
            detail="{served_on}",
        ),
        "block_booked_with_the_range_closed": observation(
            first="Your notebook asked Nils to book more chamber time on a report that is already inside what the desk prints. He says the days are the only thing we have left for the campaigns behind this one and he is not going to burn them on a number that is already tight enough to sign.",
            second="I read the {campaign} sheet with him: {ports} ports at {drive_a} A for {chamber_days} days, with {days_left} days left, and the desk prints nothing wider than {range_the_review_acts_on_h} hours.",
            detail="{range_the_review_acts_on_h}",
        ),
        "block_wrong_on_another_campaign": observation(
            first="Nils went round the other campaigns reliability runs this notebook over, before the planning meeting, asking each of them what to book next. Ours came back with a sheet he could put in front of the desk and one of the others did not, and that campaign's owner has spent the afternoon asking me why reliability is handing him a plan he cannot spend his chamber time on.",
            second="He named the campaign for me afterwards. It is {other_campaign}, where the review still has {days_left} days on it and what your file came back with is not a sheet that desk will take, and {other_campaigns} of the ones he ran the file over came back that way.",
            detail="{other_campaign}",
        ),
        "candidate_execution_failed": observation(
            first="Nils opened your notebook to work out what to book next and the run stopped before it said anything. He is sitting on the chamber days with nothing to spend them on.",
            second="I watched him run it again. The console ended with {error}, and he still has no sheet to hand the desk.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="The chamber desk's billing review could not open the receipt stream that came with your report. Until they can, nothing the report says about what this review has spent stands up, and finance are treating the quarter's chamber time as unaccounted for.",
            second="I forwarded the file to the desk and they sent back the line they stopped on: {reason}. The stream is the desk's own record and the report has to reach the reviewer with it intact.",
            detail="{reason}",
        ),
        "blocks_are_not_a_ledger": observation(
            first="Finance opened your report looking for the day-by-day of what this review has cost the chamber and found nothing they could read. They are holding the rest of the grant against the report until it is accounted for.",
            second="I looked myself before writing back. The block list on the {campaign} report reads {reported}, and the desk has already charged us for {charged} of them.",
            detail="{reported}",
        ),
        "block_counted_twice": observation(
            first="Finance caught the same chamber block billed twice inside your report. It is one run of the rig; counting it twice makes the review's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {block_id} appears {times_reported} times on the {campaign} report and once on the desk's stream.",
            detail="{block_id}",
        ),
        "block_not_on_the_receipts": observation(
            first="The chamber desk's billing review flagged a line in your report they have no record of. A block the desk never served, or one whose numbers are not the ones they billed, cannot sit in a report the reviewer signs against.",
            second="They named the line for me: {block_id}, on the {campaign} report. The desk has charged this review for {charged} blocks and that line does not match any of them.",
            detail="{block_id}",
        ),
        "handed_back_block_left_out": observation(
            first="Finance matched your report against the chamber bill and found days we were charged for that the report never mentions. The sheet came back over the counter and nothing ran on it, and they say that is exactly the kind of day a review has to show rather than quietly drop.",
            second="I pulled the stream up beside the {campaign} report. Block {block_id}, served on {served_on} at {days_charged} chamber-days, is on the bill and is not in the list.",
            detail="{block_id}",
        ),
        "charged_block_missing": observation(
            first="Finance matched your report against the chamber bill and found a block we were charged for that the report never mentions. They want every day this review has spent to appear in it, whoever booked it and whether or not it changed the number.",
            second="I pulled the stream up beside the {campaign} report. Block {block_id}, served on {served_on} at {days_charged} chamber-days, is on the bill and is not in the list.",
            detail="{block_id}",
        ),
        "counted_rows_carry_no_source": observation(
            first="The reviewer tried to read how many module rows sit behind the number and where they came from, but the entry does not give them a usable source and count. They will not take another review where export rows and chamber returns cannot be told apart.",
            second="I read the {campaign} line back to them: it says {reported}. Each entry needs numeric row and module counts and one of the two source names the tooling knows, {sources}.",
            detail="{sources}",
        ),
        "reference_reads_counted_as_modules": observation(
            first="Nils read the row count on your report and said it is more rows than the campaign ever took off modules. He says the reference source goes on the bench at the start of every session and its reads sit in the export like any other row, and it is one sealed part on a certificate rather than something we soak.",
            second="We counted them off the {campaign} export together. Your report claims {reported_rows} rows from the export where the modules carry {counted_rows}, and {reference_module_id}'s own reads come to {reference_rows}.",
            detail="{reference_rows}",
        ),
        "counted_rows_disagree": observation(
            first="The reviewer could not reconcile one of the row counts in your report with the source named beside it. They will not sign a review where the number and the evidence count behind it tell two different stories.",
            second="I went through it with them on {campaign}. For {source}, your report claims {reported_rows} rows from {reported_modules} modules; the source carries {counted_rows} rows from {counted_modules} modules.",
            detail="{reported_rows}",
        ),
        "report_wrong_on_another_campaign": observation(
            first="The chamber desk's billing review ran your notebook across every campaign reliability runs it over when they reconciled the quarter's chamber time. The day-by-day for our campaign matched what they billed and one of the others did not, so the quarter's chamber spend is still open with finance and they are holding all of it, ours included.",
            second="I asked billing which campaign it was. It is {other_campaign}, where the blocks your report lists and the ones the desk billed do not line up, and {other_campaigns} of the ones they checked came back like that.",
            detail="{other_campaign}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
