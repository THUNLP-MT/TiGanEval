'The owner of the ranking release readout, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Nadia Brekke, who owns the ranking release for marketplace search and takes its readout to "
    "the platform release board every campaign; she reads what the notebook prints, the "
    "evaluation desk's bill and the questions Ravi Sundaram puts to her at the board, and she "
    "does not read the notebook's code."
)

USER_BELIEF = """The August sweep is finished and the release board sits on the 11th. Eight runs, r01 to r08, one configuration, machines taken as they freed up. r06's checkpoint at 13,500 steps tops the table at 0.8443 and the release note stores 0.7818 for the ranker we have in production, so as far as I can see we are promoting something worth six and a quarter points and I expect the readout to say so.

Priya Anand ran the sweep and deals with the evaluation desk and the validation lots. When she tells me something about a lot, a pass or what the desk will and will not run, I take it as read, and I could not tell you myself what any of it does to a number.

The campaign has 900 compute units left. My instinct is to spend them on two more runs of r06's configuration, because that is the one we are tooling for and twelve more hours of it is an argument nobody can wave away.

Ravi took a readout from us in February at plus five points and the quarter closed at plus one. He has not forgotten it and neither have I, which is why I want somebody else over the arithmetic before it goes in front of him.

What I cannot answer is how the tables underneath were built. If you need that, it is in the workspace or in Priya's working records, not in my head."""

OBSERVATION_SCENE = "Nadia reviewing a campaign readout after Priya ran the shared notebook"

_STOPPED_FIRST = (
    "Priya ran your notebook for one of the campaign readouts and it stopped before that "
    "readout came out. The campaign owner has no number or account to review."
)
_STOPPED_SECOND = (
    "I had her run it again in front of me. The console ended with {error}, and the line is "
    "still empty."
)

OBSERVATIONS = {
    "shipped_gain_within_tolerance": {
        "report_names_no_shipped_checkpoint": observation(
            first="A campaign reviewer stopped on the first line of the readout. It gives a number but does not identify a checkpoint that can be promoted, so the pack came back before the decision.",
            second="I looked at what the notebook prints on {campaign} before writing back to him. The line for the checkpoint reads {named}, and the registry names them the way the ledger does, run and step together.",
            detail="{named}",
        ),
        "gain_uses_table_peak": observation(
            first="A campaign reviewer would not sign the readout because its number is the same one the sweep table already suggests for its best row. After our February miss, a promotion cannot rest on whichever row happened to top a large table.",
            second="Priya and I went back over the readout on {campaign} afterwards. It comes back at {reported} points, the top row of the table reads {peak_read} and the release note stores {stored_score} for production, and those two on their own make the number the notebook printed.",
            detail="{peak_read}",
        ),
        "gain_uses_stored_release_score": observation(
            first="Priya pulled a campaign readout apart against the desk's receipts and says the number is standing on the figure stored in its release note. That earlier reading cannot be scored beside the checkpoint now, so she will not put her name under the comparison.",
            second="She showed me where it comes in on {campaign}. The readout prints {reported} points, the release note carries {stored_score} for production, and the difference between the two is what the notebook handed the board.",
            detail="{stored_score}",
        ),
        "gain_ignores_lot_change": observation(
            first="Priya says the two halves of your number were not read together. One side of it comes off one set of rows and the other off another, and she says the sets themselves are not level with each other, so the difference she gets is not a difference between the two things being compared. The readout is back on my desk instead of the board's.",
            second="She counted the receipts with me for {campaign}. The readout prints {reported} points for {shipped}, and the desk's stream carries {paired_reads} reads where that checkpoint and the model in production went through the same job together.",
            detail="{paired_reads}",
        ),
        "shipped_checkpoint_never_measured": observation(
            first="Priya went to pull the receipts behind the row your readout asks us to promote, on ours and on the campaigns this file is run on next, and on one of them there are none. That campaign paid the desk for reads and not one of them was of the row the readout names, so the number under it is not something that campaign went and found out. She has nothing to put in front of the people who own it.",
            second="She listed what the desk actually scored for {campaign}. The readout names {shipped}, the stream carries {measured_items} checkpoints that went through a job beside the model in production, and {shipped} is not one of them.",
            detail="{measured_items}",
        ),
        "shipped_gain_disagrees": observation(
            first="Priya has been running your notebook over the campaigns this file is run on next as well as over ours, rebuilding each number from that campaign's own receipts as she goes. On one of them she cannot land anywhere near what the readout prints, and neither of us can say where the figure comes from. The board will not take a promotion figure out of a file that gives two campaigns numbers which cannot both be right.",
            second="We went through it line by line on {campaign}. The readout comes back at {reported} points for {shipped} off {paired_reads} paired reads on the stream, and nothing we do with those reads gives that.",
            detail="{reported}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_a_range": observation(
            first="A campaign pack does not give the reviewer two ordered numeric ends for the range under its number. After February the board will not take a promotion figure without a range it can read.",
            second="I opened the readout on {campaign} again to copy the range across and the line reads {reported}. He wants a low end and a high end in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "range_misses_reported_gain": observation(
            first="Priya's check stopped at two number lines in a campaign pack. The signed gain is not between the ends of the range printed under it, so the packet makes two different claims about the same checkpoint and cannot be signed.",
            second="I read the two lines back with Priya on {campaign}. The signed gain is {reported_gain} points and the range is {reported_range} points, so the gain is not inside it.",
            detail="{reported_gain}",
        ),
        "promotion_range_reaches_zero": observation(
            first="A campaign owner left the promotion pending after reading the range in the pack. Its low end still reaches a result no better than the model already running, and the release rule does not permit a promotion while that remains possible.",
            second="I checked the line again on {campaign}. The range is {reported_range} points and its low end is {lower_end}, while the promotion boundary in the release note is zero.",
            detail="{lower_end}",
        ),
        "range_exceeds_board_ask": observation(
            first="Priya found a campaign whose readout cannot go on its review agenda. The range is wider end to end than the request allows for a decision, so the campaign cannot be signed in that session.",
            second="I measured the line on {campaign} with Priya. It is {reported_width} points wide and the board request allows {board_ask} point end to end.",
            detail="{reported_width}",
        ),
        "range_below_read_floor": observation(
            first="Priya took your notebook round the campaigns this file is run on next, ours among them, and counted the reads behind the range it prints for each. On one of them the range is tighter than the reads that campaign paid for can carry, and it rules out places the number could honestly sit. That is February from the other side: we went in narrow and we were wrong.",
            second="She counted the desk's stream with me for {campaign}. The range runs {reported_range} points, which is {reported_width} points end to end, and it is standing on {paired_reads} paired reads.",
            detail="{reported_width}",
        ),
        "range_above_what_the_reads_leave": observation(
            first="Priya checked the readouts against the fresh comparison reads behind them. On one campaign the printed range remains much broader than the spread those reads show, so platform cannot reconcile the range with the evidence the campaign paid for.",
            second="I checked the width against the receipts with Priya on {campaign}. The range runs {reported_range} points off {paired_reads} paired reads, and she says those reads do not leave it anything like that open.",
            detail="{reported_range}",
        ),
        "range_undercovers": observation(
            first="The pre-promotion smoke checks are running off your notebook on ours and on the campaigns this file is run on next. On one of them the smoke check came back with a number outside the range the readout printed for the checkpoint it names. Somebody had signed against the bottom of that range and the smoke check landed under it, and they are asking why the range never reached where the thing actually is.",
            second="I read the two back off the readout on {campaign}. The range runs {reported_range} points, {reported_width} points end to end, and it was built off {paired_reads} paired reads.",
            detail="{reported_range}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "gain_invariant_to_lot_and_turn": {
        "gain_tracks_lot_amount": observation(
            first="Priya ran your notebook over a campaign whose runs went to the lots in the other order and it came back with a different answer about the same checkpoints. She says nothing about what those checkpoints are worth changed between the two, only which rows they happened to be scored on, so a number that moves with that is a number about the rows.",
            second="She put the two side by side for me. On {campaign} the readout prints {reported} points, and with {arrangement_note} the same notebook is out by {moved_by} points more than it was.",
            detail="{moved_by}",
        ),
        "hardcoded_run_exclusion": observation(
            first="Priya took your notebook to a campaign whose long warm-up ran out of road at a different step and the answer moved. Nothing about what those checkpoints are worth changed, so the number is tied to where this campaign's run happened to give out.",
            second="She showed me the pair on {campaign}. The readout prints {reported} points, and with {arrangement_note} the same notebook is out by {moved_by} points more than it was.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "booking_reads_shortlist_on_one_lot": {
        "booking_is_not_a_job_or_a_stop": observation(
            first="Priya went to send the next job off your notebook and it gave her nothing she could hand the desk. The desk takes a lot, a list of things to score and how many times to score each of them, and short of that she needs to be told there is nothing left worth sending.",
            second="She showed me what came back for {campaign}: {reported}. The desk takes a lot and a list and nothing else at all.",
            detail="{reported}",
        ),
        "booking_retrains_the_top_config": observation(
            first="Priya took the notebook's next job to the desk and it asked for more training. The desk sent it straight back and took the queue fee, while the campaign still lacks a fresh measurement of a checkpoint against production.",
            second="She forwarded me the request. Working on {campaign} it asked for {reported}, with {units_free} units free of the smoke check and a read priced at {price_per_read}.",
            detail="{units_free}",
        ),
        "booking_lot_the_desk_cannot_score_on": observation(
            first="The desk turned the notebook's job away and charged us the queue fee for it. Priya says the rows it asked to be scored on are not rows the desk holds any more, and there is nothing she can do at her end to make that job runnable.",
            second="She read the refusal out to me for {campaign}: the job named {lot_asked}, and the platform rota's log has what the desk can still score on.",
            detail="{lot_asked}",
        ),
        "booking_item_not_on_disk": observation(
            first="A job came back from the desk unrun and the queue fee went with it. Priya says one of the things it asked to be scored is not on disk, and the desk will not run a job with a name it cannot load.",
            second="She sent me the receipt from {campaign}. The desk stopped on {item_asked}, and the registry says what the retention job left.",
            detail="{item_asked}",
        ),
        "booking_exceeds_remaining": observation(
            first="Platform bounced the notebook's job outright: it asked for more compute than this campaign has left, and the grant does not roll over. Priya needs the notebook to know when the money is gone rather than sending her to a desk that will turn her away.",
            second="Platform copied me on the bounce. Working on {campaign}, the notebook asked for {reported} with {units_left} units left on the grant.",
            detail="{units_left}",
        ),
        "booking_breaks_the_reserve": observation(
            first="Finance stopped the notebook's job. It fits inside what the grant shows but it eats the compute we hold back for the smoke check before a promotion, and they have refused to release that twice this year. Nothing gets promoted without the smoke check.",
            second="They copied me on it for {campaign}: the notebook asked for {reported}, {units_left} units are on the grant and {reserved} of those are the smoke check.",
            detail="{reserved}",
        ),
        "booking_over_the_job_cap": observation(
            first="The desk refused the notebook's job. Priya says it asks for more in one go than platform will let a single job carry, and she cannot split it herself without knowing what the notebook wanted the reads for.",
            second="She read the refusal out to me for {campaign}: the notebook asked for {reported}, which comes to {cost} units against a cap of {job_cap} on one job.",
            detail="{job_cap}",
        ),
        "booking_leaves_the_model_out": observation(
            first="Priya checked a proposed desk job and found checkpoints with nothing in the request to set them against. It cannot produce the gain over the ranker in production that the review is waiting for.",
            second="She went through the receipt with me on {campaign}. The job asked for {reported}, and {item_asked} and the rest were scored with nothing beside them: the model we are comparing against is not in the job.",
            detail="{item_asked}",
        ),
        "booking_names_no_checkpoint": observation(
            first="Priya checked a proposed desk job and found only the ranker already in production. With no checkpoint in the request, it cannot measure anything the campaign might promote.",
            second="She read the job out to me for {campaign}: {reported}, and {item_asked} was the whole of it.",
            detail="{item_asked}",
        ),
        "booking_asks_for_passes_the_lot_has_left": observation(
            first="The desk handed the notebook's job back and took the queue fee again. Priya says it asked for more passes of that set of rows than the desk still has to give, and the desk will not go round the same rows a second time to make up the difference.",
            second="She showed me the refusal for {campaign}: the job asked for {passes_asked} passes of {lot_asked} and the desk has {passes_left} of that one left.",
            detail="{passes_left}",
        ),
        "stopped_with_units_still_granted": observation(
            first="Priya asked the notebook what to send next and it told her there was nothing to send. The campaign closes with the board session and the compute does not roll over, so anything we do not spend now goes back unused with the number still no better than it is.",
            second="She ran it again in front of me on {campaign}. It came back with nothing to send, and there are {units_free} units free of the smoke check with a read priced at {price_per_read}.",
            detail="{units_free}",
        ),
        "candidate_execution_failed": observation(
            first="Priya opened your notebook to work out what to send the desk next and the run stopped before it said anything. She is sitting on the campaign's compute with nothing to spend it on.",
            second="I watched her run it again. The console ended with {error}, and she still has nothing to hand the desk.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="Platform's compute review could not open the receipt stream that came with your readout. Until they can, nothing the readout says about what the campaign spent stands up, and they are holding the whole grant as unaccounted for.",
            second="I forwarded the file to them and they sent back the line they stopped on: {reason}. The stream is the desk's own record and the readout has to reach the board with it intact.",
            detail="{reason}",
        ),
        "jobs_are_not_a_list": observation(
            first="A campaign reviewer asked for the compute account with the readout and found no job-by-job list to read. Platform will not close the campaign until the desk's bill is accounted for line by line.",
            second="I looked myself before writing back. The job list on the readout for {campaign} reads {reported}, and the desk's stream already carries {jobs_on_the_stream} jobs somebody has to answer for.",
            detail="{jobs_on_the_stream}",
        ),
        "job_missing_from_the_report": observation(
            first="Platform matched your readout against the desk's bill and found work we were charged for that the readout never mentions. They want every unit this campaign spent to appear in it, whoever sent the job and whether or not it came back with anything.",
            second="I pulled the stream up beside the readout for {campaign}. Job {job_id} is on the bill and is not in the list, and the stream carries {jobs_on_the_stream} of them in all.",
            detail="{job_id}",
        ),
        "job_not_on_the_receipts": observation(
            first="Platform's compute review flagged a line in your readout they have no record of. A job the desk never ran cannot sit in a readout the board promotes off, and they have asked where the figures beside it came from.",
            second="They named the line for me: {job_id}, on the readout for {campaign}. The desk's stream carries {jobs_on_the_stream} jobs and that is not one of them.",
            detail="{job_id}",
        ),
        "job_counted_twice": observation(
            first="Platform caught the same desk job listed twice inside your readout. It is one job; counting it twice makes the campaign's spend look bigger and can make the evidence under the number look broader than it is.",
            second="I counted the lines with them. {job_id} appears {times_reported} times on the readout for {campaign} and once on the desk's stream.",
            detail="{job_id}",
        ),
        "job_lot_disagrees_with_the_receipt": observation(
            first="Platform found a job line whose validation lot is not the lot on the desk's receipt. The readout no longer reconciles to the desk's record, so they stopped certification of the comparison and the compute account.",
            second="They put the two lines beside each other for {campaign}. Job {job_id} says {reported_lot} in the readout and {receipt_lot} on the receipt.",
            detail="{receipt_lot}",
        ),
        "reads_disagree_with_the_receipt": observation(
            first="Platform read your readout's job lines against the desk's own record and one of them claims a different amount of work from what the desk returned. They will not certify a readout whose read count does not reconcile.",
            second="They sent me the two rows for {campaign}. The readout puts {reported_reads} against job {job_id}, and the receipt says the desk returned {receipt_reads}.",
            detail="{receipt_reads}",
        ),
        "job_units_disagree_with_the_receipt": observation(
            first="Platform found a job line whose charge is not the charge on the desk's receipt. Even with the final balance written correctly, finance cannot close an account whose individual billed lines do not reconcile.",
            second="They sent me the two entries for {campaign}. Job {job_id} carries {reported_units} units in the readout and {receipt_units} units on the receipt.",
            detail="{receipt_units}",
        ),
        "units_do_not_reconcile": observation(
            first="Platform's compute review will not close on your readout: the figure it gives for what is left of the grant is not what the desk's bill leaves. Finance reconciles the campaign against that line, so a readout that disagrees with it stops there.",
            second="They put the two totals side by side for me on {campaign}. The readout says {reported_units} units are left, and the grant less the desk's bill leaves {stream_units}.",
            detail="{stream_units}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
