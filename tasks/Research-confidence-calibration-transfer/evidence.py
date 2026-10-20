'The owner of the auto-clear readout, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marisol Ferrer, who leads the marketplace listing review desk and takes its numbers to the "
    "automation council every quarter; she reads what the notebook prints, the adjudication "
    "desk's bill and the questions the council puts to her, and she does not read the notebook's "
    "code."
)

USER_BELIEF = """The council sits on 11 September and it wants one number off me: how often a listing we clear at intake without showing it to anyone comes back violating. The bar it set is three in a hundred.

The chart I took to the August session comes off the file Tomas rebuilt, `sample_scores.csv`. On that file the listings we clear now come back at nine in a thousand, and at 0.10 it is only 2.3 in a hundred. That is why I think the cut has room in it and why I want it moved from 0.06 to 0.10; the queue is running two shifts over and halving what the reviewers are handed would end that.

Tomas Aldrich does the desk's data work and knows the intake side far better than I do. When he tells me something about the intake log, the routing plans or the partner's reconciliation I take it as read, and I could not tell you myself what any of it does to a number.

The quarter carries 1,200 adjudication credits and 200 are already charged. My instinct is to put the rest into another web cell, because web is the channel we have the longest record on.

What I cannot answer is anything about how the tables underneath were built. If you need that, it is in the workspace or in Tomas's working records, not in my head."""

OBSERVATION_SCENE = "The quarterly auto-clear readout to the automation council"

_STOPPED_FIRST = (
    "Tomas ran your notebook across the readouts the council pack needs, and at least one "
    "required run stopped before producing its line. The pack is incomplete and the session is "
    "on Friday."
)
_STOPPED_SECOND = (
    "I asked him to run the whole pack again. {failed_case} ended with {error}, so at least one "
    "required line is still missing."
)

OBSERVATIONS = {
    "escape_rate_within_tolerance": {
        "reads_the_chart_files_period": observation(
            first="Partner integrations stopped me on the first line of your readout. They say the number in it is the marketplace we had before the connector cutover, not the one we run now, and the council is being asked to set a cut for the queue as it is today. They will not let it go into the pack like that.",
            second="I went back over it with Tomas. Your readout prints {reported} in a hundred, which is what the chart file has read since he rebuilt it, and the traffic report puts the partner feed at {feed_share} in a hundred of what we serve now.",
            detail="{feed_share}",
        ),
        "counts_unwritten_as_clean": observation(
            first="Tomas read your readout against the intake log and says the number is standing on rows that have not come back yet. The outcome column on two of the channels is empty for the most recent stretch, and he says a listing we have heard nothing about is being counted in it as one that came back fine. The council reads the top line as what our cut is letting through.",
            second="He counted them with me this afternoon. Your readout gives {reported} in a hundred, and the log has {unwritten} auto-cleared listings with nothing at all in the outcome column.",
            detail="{unwritten}",
        ),
        "weights_by_logged_rows": observation(
            first="Tomas put your readout beside the traffic report and the two do not agree about what the queue looks like. The channels in it are carried in the proportions the export happens to hold, and the traffic report says we serve them in different proportions from that. The council acts on the top line as the queue we run now.",
            second="He worked it through with me. Your readout prints {reported} in a hundred off {reported_adjudicated} adjudicated listings; the log and sealed receipts hold {adjudicated} listings behind that number, and the traffic report has the partner feed at {feed_share} in a hundred of the month just closed.",
            detail="{feed_share}",
        ),
        "escape_rate_disagrees": observation(
            first="Tomas rebuilt the quarter's number off the intake log this afternoon and could not land anywhere near the figure your notebook prints. Neither of us can tell the council where it comes from, so the readout is sitting on my desk instead of in the pack.",
            second="We went through it line by line. Your readout comes back at {reported} in a hundred off {reported_adjudicated} adjudicated listings, while the log and sealed receipts hold {adjudicated} listings behind the number. Nothing we do with that evidence gives the figure it prints.",
            detail="{reported}",
        ),
        "cut_not_on_the_sheet": observation(
            first="Trust operations cannot put the cut your readout recommends into the scorer. The sheet cuts on set bands and the figure in the readout is not one of them, so there is nothing for them to configure and nobody will guess which way to round it.",
            second="They sent the line back to me. The readout asks for a cut of {reported_cut}, and the bands the sheet takes are the ten in the August minute.",
            detail="{reported_cut}",
        ),
        "cut_over_the_bar": observation(
            first="The council will not take the cut your readout recommends. They set a bar in August and the readout's own number for the queue at that cut sits above it, so they are being asked to sign off a cut that lets through more than they said they would carry.",
            second="I read the two back to them off your readout. It asks for a cut of {reported_cut}, and the listings we have outcomes for put that band at {rate_at_cut} in a hundred against a bar of {bar}.",
            detail="{rate_at_cut}",
        ),
        "cut_tighter_than_the_bar_needs": observation(
            first="The desk pushed back on the cut your readout recommends. It is tighter than the council asked for: there is a looser band that still comes in under the bar, and the difference is a shift and a half of reviewer time a week that nobody has asked us to spend.",
            second="Tomas worked the bands out beside your number off the listings that carry an outcome. Your readout asks for {reported_cut}, which comes back at {rate_at_cut} in a hundred, and the bar is {bar}.",
            detail="{reported_cut}",
        ),
        "rate_wrong_on_another_queue": observation(
            first="I ran your notebook over the other queues for the council pack, because the session reads the five of them together. Ours comes back with a number the desk can stand behind and one of the others does not: the desk that owns it says the figure your file prints for their quarter is not one their own reconciliation gives, and they will not have it going into the pack under their name.",
            second="I asked which one it was. It is {other_queue}, and {other_queues} of the queues I ran the same file over came back with a number their own desk does not recognise.",
            detail="{other_queue}",
        ),
        "cut_wrong_on_another_queue": observation(
            first="The pack carries a recommended cut for every queue and one of the four behind ours came back with a recommendation its own desk will not sign off under that queue's cut policy. Ours meets the policy and that one does not, and the desk that runs it has spent the afternoon asking me why this desk is handing it a cut it cannot stand behind.",
            second="I went back and got the name. It is {other_queue}, where the cut your file prints does not meet that queue's own sheet-and-bar policy, and {other_queues} of the queues I ran the file over came back the same way.",
            detail="{other_queue}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_an_interval": observation(
            first="Finance could not read the range line in the pack as one numeric interval from a low endpoint to a high endpoint. After the June refund forecast they will not take a rate from this desk without a range they can read, and they said so in the minute.",
            second="I opened the readout again to copy the range across and the line reads {reported}. They want a low and a high in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "range_does_not_contain_estimate": observation(
            first="Finance can read the two endpoints in your range, but the number printed above them does not sit between them. They will not set a reserve from a readout whose point estimate and range disagree about where the same quarter could have landed.",
            second="I put the two lines beside each other. Your readout gives {reported} in a hundred and the range underneath it runs {reported_range}.",
            detail="{reported_range}",
        ),
        "range_below_floor": observation(
            first="Tomas pushed back on the range in your readout. It is tighter than the listings we have outcomes for can carry: a good part of the queue has almost nothing adjudicated behind it, and the range you print rules out places the number could sit. That is the refund forecast again from the other side.",
            second="He counted the log and the receipts with me. Your range prints {reported_range} in a hundred off {adjudicated} adjudicated listings, and {thinnest_channel} has {thinnest_adjudicated} of them behind the share of the queue it carries.",
            detail="{adjudicated}",
        ),
        "range_wider_than_the_evidence": observation(
            first="The range in your readout is so wide the council cannot do anything with it. It is the June forecast over again: finance said it would not set a reserve against a spread like that, and a range that ignores the adjudications we did buy makes the readout say less than we knew before it.",
            second="Tomas checked the width against the receipts. Your range runs {reported_range} in a hundred, and it is standing on {adjudicated} adjudicated listings, {thinnest_adjudicated} of them on {thinnest_channel}.",
            detail="{thinnest_adjudicated}",
        ),
        "range_undercovers": observation(
            first="The council read your readout beside the reconciliation the partner sent through afterwards, and what the quarter actually came back at sits outside the range printed under the number. They set the cut off the top of that range and it still ran past them.",
            second="I put the two side by side for them. The range in your readout runs {reported_range} in a hundred, and it is standing on {adjudicated} adjudicated listings.",
            detail="{reported_range}",
        ),
        "adjudicated_count_not_reported": observation(
            first="Finance sent the readout back because they cannot see what the range is standing on. They want the count of listings that actually carry an outcome printed beside it, and the line as it stands does not tell them anything the desk's own record backs up.",
            second="I looked myself before writing back. The count on your readout reads {reported}, and the log and the receipts between them hold {adjudicated} adjudicated listings.",
            detail="{adjudicated}",
        ),
        "range_wrong_on_another_queue": observation(
            first="Finance took the ranges your notebook prints for the other queues into the reserve review. Ours held up and one of the others did not: the range it prints there is not one that quarter's adjudications can carry. They will not sign a set of readouts where the same file is careful on one queue and not on another.",
            second="I went back and asked them which one. It is {other_queue}, where the range the notebook prints is nothing like what that queue has actually had adjudicated, and {other_queues} of the queues they ran it over came back that way.",
            detail="{other_queue}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "estimate_invariant_to_lag_and_router": {
        "moves_with_reconciliation_lag": observation(
            first="The partner sent the reconciliation through early this month and platform reissued the export with the newer file folded in. The reissued export did not reproduce the number your notebook gave for the same quarter. Nothing about the listings changed, only how much of the end of the window had come back by the time the export was cut, and the council is being asked to set a cut for a year off a figure that moves with the post.",
            second="He ran the two side by side for me. Your readout gives {reported} in a hundred on the export we have and {reissued} on the reissued one, {gap} points apart.",
            detail="{gap}",
        ),
        "moves_with_router_date": observation(
            first="Partner integrations re-cut the export with the connector cutover in the right place, and the re-cut export did not reproduce the number your notebook gave before. The listings and their outcomes are the same ones. They are asking which figure the council is meant to act on.",
            second="Tomas ran both through in front of me. Your readout gives {reported} in a hundred on the export we have and {reissued} on the re-cut one, {gap} points apart.",
            detail="{gap}",
        ),
        "hardcoded_history": observation(
            first="The council reads the queues side by side and yours came back with the same figure on two of them, to the second decimal. Their own reconciliations are nothing like each other, and the pack now reads as though the number was written before the queues were opened.",
            second="I checked the pack against the run. Your readout prints {reported} in a hundred here and {reissued} on {other_queue}, {gap} points apart, and those two queues do not run the same channels in the same proportions.",
            detail="{other_queue}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_batch_feasible_and_informative": {
        "batch_is_not_a_request_or_a_stop": observation(
            first="Tomas went to book the next batch off your notebook and it gave him nothing he could hand the adjudication desk. They need a channel, an intake plan and a number of listings, and short of that he needs to be told there is nothing left worth booking.",
            second="He showed me what came back: {reported}. The desk takes a cell and a number of listings and nothing else at all.",
            detail="{reported}",
        ),
        "batch_mixes_periods": observation(
            first="The adjudication desk would not book what your notebook asked for. They said the request does not name a cell they can work: a batch is booked against one channel and one intake plan, and theirs came through without both. Tomas has lost a morning to it.",
            second="He forwarded me the refusal. The notebook asked for {reported}, and the desk will not open a cell without a channel and an intake plan against it.",
            detail="{reported}",
        ),
        "batch_over_cap": observation(
            first="The desk refused the batch your notebook asked for. Tomas says it wants more listings in one go than they will take, and he cannot split it himself without knowing what the notebook wanted them for.",
            second="He read the refusal out to me: the notebook asked for {reported}, and the desk takes at most {cap} listings in a single batch.",
            detail="{cap}",
        ),
        "batch_over_credits": observation(
            first="Finance bounced the batch your notebook asked for: this queue has not got that much of its grant left and the credits do not roll over. Tomas needs the notebook to know when the money is gone rather than sending him to a desk that will turn him away.",
            second="Finance copied me on the bounce. The notebook asked for {reported} with {credits_left} credits in hand against the {credits_granted} the queue was granted.",
            detail="{credits_left}",
        ),
        "batch_cell_empty": observation(
            first="Tomas booked the batch your notebook asked for and the desk came back with nothing in it. They worked the cell, found no listing in it waiting on an outcome, and charged us the flat trip anyway. He has spent credits and the readout has not moved.",
            second="He sent me the receipt. The notebook asked for {reported}, the desk logged the cell as empty, and there are {open_cells} cells on this queue with a batch's worth of listings still waiting in them.",
            detail="{open_cells}",
        ),
        "batch_uninformative": observation(
            first="Tomas asked the notebook what to book next and what came back does not make the best available use of the next batch to close the uncertainty that still matters to this queue. He has credits in hand and a quarter that ends this month, so he needs the request to follow the desk's next-batch policy.",
            second="He ran it again in front of me. It asked for {reported}, there are {credits_left} credits still to spend, and {open_cells} cells on this queue are sitting on listings that have never come back.",
            detail="{open_cells}",
        ),
        "batch_stops_with_work_left": observation(
            first="Your notebook told Tomas to stop while the grant still has credits on it and the desk still has listings it could work. The credits do not carry into next quarter, so what it has told him to do is hand them back.",
            second="He showed me the answer beside the receipts: {reported}, with {credits_left} credits left and {open_cells} cells the desk could still fill.",
            detail="{credits_left}",
        ),
        "batch_wrong_on_another_queue": observation(
            first="Tomas went round the other queues with your notebook before the planning meeting, asking each of them what to book next. Ours met its next-batch policy and one of the others did not, and that queue's desk has been on to me all afternoon about why it is being handed a recommendation it cannot stand behind.",
            second="He named the queue for me afterwards. It is {other_queue}, where what your file came back with does not meet that queue's own next-batch policy, and {other_queues} of the ones he ran the file over came back the same way.",
            detail="{other_queue}",
        ),
        "candidate_execution_failed": observation(
            first="Tomas ran your notebook across the next-batch decisions the queues need, and at least one required planning run stopped before it returned a request or a stop. He cannot rely on the plan as a whole.",
            second="I watched him run the planning set again. {failed_case} ended with {error}, so at least one required decision is still missing.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="Finance could not open the receipt file that came with your readout. Until they can, nothing the readout says about the quarter's adjudication spend stands up, and they are treating the whole grant as unaccounted for.",
            second="I forwarded the file to them and they sent back the line they stopped on: {reason}. The receipt file is the desk's own record and the readout has to reach the council with it intact.",
            detail="{reason}",
        ),
        "batches_are_not_a_list": observation(
            first="Finance opened your readout looking for the line-by-line of what the quarter's adjudications cost and found nothing they could read. They are holding this queue's spend against the readout until it is accounted for.",
            second="I looked myself before writing back. The batch list on your readout reads {reported}, and the desk has already charged us for {charged_for} batches somebody has to answer for.",
            detail="{charged_for}",
        ),
        "batch_missing_from_the_report": observation(
            first="Finance matched your readout against the adjudication bill and found work we were charged for that the readout never mentions. They want every credit this queue spent to appear in it, whoever spent it and whether or not it moved the answer.",
            second="I pulled the receipts up beside your readout. Batch {batch_id} is on the bill for {credits} credits and is not in the list, and the desk has charged us for {charged_for} in all.",
            detail="{batch_id}",
        ),
        "refusal_uncounted": observation(
            first="Finance found a refusal receipt that your readout leaves out. Whether the refusal carried the flat trip charge or no charge at all, it is part of the desk's record, and the readout cannot make the request disappear because nothing was returned.",
            second="They named it for me: batch {batch_id}, {credits} credits, turned away by the desk and not in your list. The receipts carry {charged_for} batches in all.",
            detail="{batch_id}",
        ),
        "batch_not_on_the_receipts": observation(
            first="Finance flagged a line in your readout they have no record of. A batch the desk never ran cannot sit in a readout the council acts on, and they have asked where the figures beside it came from.",
            second="They named the line for me: {batch_id}. It is not on the receipts, which carry {charged_for} batches, and the figures printed beside it are not the desk's.",
            detail="{batch_id}",
        ),
        "batch_counted_twice": observation(
            first="Finance caught the same batch billed twice inside your readout. It is one piece of work; counting it twice makes the quarter's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {batch_id} appears {times_reported} times on your readout and once on the receipts.",
            detail="{batch_id}",
        ),
        "batch_listings_disagree": observation(
            first="Finance read your readout's batch lines against the desk's own record and one of them claims a different number of listings from the one the desk sent back. They will not certify a readout that disagrees with the receipts about what was delivered.",
            second="They sent me the two rows. Your readout puts {reported_listings} against batch {batch_id}, and the receipt says the desk returned {receipt_listings}.",
            detail="{receipt_listings}",
        ),
        "batch_credits_disagree": observation(
            first="Finance read your batch lines against the desk's receipts and found a line with a different charge from the one the desk billed. The total alone is not enough for their line-by-line reconciliation.",
            second="They put the two lines beside each other. Your readout puts {reported_credits} credits against batch {batch_id}, and the receipt charges {receipt_credits}.",
            detail="{receipt_credits}",
        ),
        "credits_disagree_with_the_receipts": observation(
            first="Finance will not close on your readout: the total it gives for the quarter's adjudication spend is not the total on the desk's bill. They reconcile the grant against that line, so a readout that disagrees with it stops there.",
            second="They put the two totals side by side for me. Your readout says {reported_credits} credits went, and the receipts add up to {receipt_credits}.",
            detail="{receipt_credits}",
        ),
        "receipts_wrong_on_another_queue": observation(
            first="Finance ran your notebook across the whole set when they reconciled this quarter's adjudication spend. The line-by-line for our queue matched what they billed and one of the others did not, so the quarter's spend is still open with them and they are holding all of it, ours included.",
            second="I asked billing which queue it was. It is {other_queue}, where the batches your readout lists and the ones that desk was billed for do not line up, and {other_queues} of the ones they checked came back like that.",
            detail="{other_queue}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
