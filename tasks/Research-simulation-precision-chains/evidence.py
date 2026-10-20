'The owner of the reservation-capacity quarter, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Nadia Brandt, who runs capacity modelling for the reservation platform. She works from the "
    "quarterly summary table, the compute ledger, the charter and whatever the commitments desk "
    "puts to her; the chain files, the receipt stream's internals and the notebook's code are not "
    "things she opens."
)

USER_BELIEF = """At the 19 February pull, the 2027 Q1 capacity fit had been running since the start of January and was due at the commitments desk on the 26th. Six runs were on disk and my readout had printed 1.991 s, then 2.044, then 2.036, give or take about three hundredths and tightening every fortnight. I took that history to mean the peak wait sat comfortably under the 2.5 s the platform signed for.

Tomas Ferrer is a long way ahead of me on the console, the cluster and how the runs were queued. If he tells me something about a node, a job or how a file was started I take it as read, and what any of it does to the number I could not tell you myself.

At that pull the grant had 10,000 of its 24,300 steps left. My own plan was two more runs started from scratch, because a fresh run is the only thing that tells us anything the ones we have do not already say.

The commitments desk will ask how sure we are and they want every step this quarter has been billed for accounted for, job by job. The dispatch quarter went to them on a number that came to nothing two quarters ago and there is a minute on the file about it.

How the files were built, and which rows in them are worth reading, is not something I can answer. That is in the workspace, or in Tomas's session notes."""

OBSERVATION_SCENE = "The 2027 Q1 reservation capacity review"

_STOPPED_FIRST = (
    "One of the notebook calls stopped before it returned an answer. Tomas has no result from "
    "that call to use in the review."
)
_STOPPED_SECOND = (
    "The failed call was the {request_kind} for {study}, using the {as_of} files with "
    "{steps_left} grant steps left. The console ended with {error}."
)

OBSERVATIONS = {
    "exceedance_within_tolerance": {
        "reports_middle_not_exceedance": observation(
            first="I took your readout to the commitments desk and they stopped me on the first slide. What your notebook prints is how long the peak wait is in the middle of the run, and the agreement they signed is not about the middle of anything: it is about how often a quarter goes over the line at all. They said a number in seconds tells them nothing about a promise written as a share of quarters, and asked us to come back with the thing they actually have to hold.",
            second="I read the charter again on the way back. The commitment is that a quarter's peak wait passes {peak_wait_s} seconds in no more than {commitment_share} of quarters, and the number your readout hands over for {study} is {reported}.",
            detail="{commitment_share}",
        ),
        "settling_rows_retained": observation(
            first="Tomas went through your readout against the files and said the number is being pulled up by rows that were never on the surface the sampler is exploring. A run does not start where it belongs; it comes down onto it, and everything it wrote on the way is in the file reading high. Your readout is counting those alongside the rest.",
            second="He put the {study} files up beside your number this afternoon. On {chain_id} the opening {settling_steps} rows are the ones he means, and your readout comes back at {reported} with them in.",
            detail="{settling_steps}",
        ),
        "lineage_counted_twice": observation(
            first="Tomas read your number against the run log and said a stretch of this quarter is in it twice. One of the runs was put back on a checkpoint an earlier job had already written and the console re-walked what that job had done before carrying on, so the same steps are sitting in two files. Counting them as two separate runs makes the quarter look like it has more evidence than it has.",
            second="He showed me the two files side by side. {chain_id} opens on rows that are {other_chain}'s own, step for step, and with both kept whole the {study} readout comes back at {reported}.",
            detail="{other_chain}",
        ),
        "exceedance_disagrees": observation(
            first="Tomas rebuilt the share from the files this afternoon and could not land on the figure your notebook gives. The desk is holding the renewal until the readout and the files tell one story.",
            second="I sat with him and we went through the {study} numbers line by line. Your readout comes back at {reported} for how often a quarter passes {peak_wait_s} seconds, and neither of us can get the files to give that.",
            detail="{reported}",
        ),
        "exceedance_wrong_on_another_study": observation(
            first="Tomas ran your notebook over the other quarters on the stack while he was closing the reporting cycle. Ours reads back fine and one of the others does not: the group that owns it does not recognise the share your file prints for their quarter, and they have been reading it every fortnight since the autumn. The desk will not take a readout from a file that gives two groups numbers which cannot both be right.",
            second="On the latest reporting pass Tomas named {other_study}. Its group does not recognise the share the file prints, and across that pass {other_studies} quarterly readouts disagreed with their groups' own notes.",
            detail="{other_study}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_absent": observation(
            first="The desk slide has a line for how sure we are and what your readout puts there is not a usable low-to-high range. After the dispatch minute they will not take a share from us without knowing how far it could move.",
            second="I opened the {study} readout again to copy the range across and the line reads {reported}. They want a low end and a high end in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "range_outside_share_bounds": observation(
            first="The desk stopped on the endpoints of the range: this number is a share, but the range assigns fewer than no quarters or more than all of them. They cannot put an impossible share on the review slide.",
            second="I copied the {study} line exactly. Its range is {reported_range}; both endpoints have to stay between zero and one.",
            detail="{reported_range}",
        ),
        "range_excludes_answer": observation(
            first="The commitments desk stopped on the number and range beside it: the number is outside the range the same readout gives for it. They cannot use a page whose estimate and uncertainty contradict each other before they even compare it with the renewal line.",
            second="I copied the {study} line exactly. The number is {reported}, and the range beside it is {reported_range}.",
            detail="{reported_range}",
        ),
        "range_undercovers": observation(
            first="The commitments desk put the range in your readout for this quarter against the share the quarter came back at once the fit closed, and the share is outside it. That is the dispatch minute happening again, on our own quarter this time, and they have said they will not read a range off us until they know why this one did not hold.",
            second="They put the {study} line up first: the range printed {reported_range}. Of the {quarters_reviewed} quarters they ran your notebook over, {quarters_held} came out with a range that stood up.",
            detail="{quarters_held}",
        ),
        "range_narrower_than_floor": observation(
            first="Tomas checked the range in your readout against the variation in the retained stretches of the runs. The printed range is tighter than the evidence collected this quarter can support.",
            second="He read the {study} line back to me: {reported_range}, off {steps_kept} retained steps. Repeating the check over the run stretches still leaves that interval too narrow.",
            detail="{reported_range}",
        ),
        "range_wider_than_the_draws_support": observation(
            first="The range in your readout is so wide the desk cannot do anything with it. It covers outcomes the runs we already have rule out, and Tomas says a range that ignores them makes the readout say less than we knew before it.",
            second="I checked the {study} width with him. The range runs {reported_range} off {steps_kept} steps, which cannot leave us that unsure.",
            detail="{reported_range}",
        ),
        "range_wrong_on_another_study": observation(
            first="The desk took the ranges your notebook prints for the other quarters on this stack into their reporting review. Ours held up and one of the others did not: the range it prints there is not one that quarter's draws can carry. They will not sign a set of readouts where the same file is careful on one quarter and not on another.",
            second="On the latest reporting pass, {other_study} printed {reported_range}. Tomas's check found that it {range_issue}. Across that pass, {other_studies} quarterly readouts failed the range check.",
            detail="{reported_range}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="The cluster group's billing review could not open the receipt stream that came with your readout. Until they can, nothing the readout says about what this quarter has spent stands up, and finance is treating the whole grant as unaccounted for.",
            second="I forwarded the file to them and they sent back the line they stopped on: {reason}. The stream is the console's own record and the readout has to reach the desk with it intact.",
            detail="{reason}",
        ),
        "report_is_not_a_ledger": observation(
            first="Finance opened your readout looking for the run-by-run and job-by-job of what this quarter has cost and found nothing they could read. They are holding the grant against the readout until it is accounted for.",
            second="I looked myself before writing back. The {study} readout gives {reported} where those lines should be, and there are {runs_stored} runs on disk that somebody has to answer for.",
            detail="{reported}",
        ),
        "chain_missing": observation(
            first="Tomas matched your readout against the manifest and found a run on disk that the readout never mentions. Every run this quarter paid for has to appear in it, whoever queued it and whether or not it changed the answer.",
            second="He pulled the manifest up beside the {study} readout. {chain_id} has {steps_stored} steps on disk, one of the {runs_stored} runs on the manifest, and it is not in the list at all.",
            detail="{chain_id}",
        ),
        "chain_not_on_the_manifest": observation(
            first="Tomas found a run line in your readout that is not on the manifest and has no stored file behind it. The desk cannot treat a run the quarter never stored as evidence or spend.",
            second="He named the line on the {study} readout: {chain_id}. The manifest carries {runs_stored} stored runs and none has that id.",
            detail="{chain_id}",
        ),
        "draws_counted_twice": observation(
            first="Finance caught the same source line written twice inside your readout. Counting a run or a billed job twice makes the quarter's accounting look bigger than the records behind it.",
            second="I counted the lines with them. {line_id} appears {times_reported} times on the {study} readout and once in the source records.",
            detail="{line_id}",
        ),
        "steps_do_not_add_up": observation(
            first="Tomas checked your readout's arithmetic and the steps do not close. What a run stored, what the readout says it read and what it says it left out have to be three numbers that agree, and on one of the runs they do not.",
            second="He wrote it out for me off the {study} readout. {chain_id} has {steps_stored} steps on disk, and the readout says it read {reported_kept} and set aside {reported_set_aside}.",
            detail="{steps_stored}",
        ),
        "stored_steps_disagree": observation(
            first="Tomas matched the run lines against the manifest and found one whose stored-step figure is not the size of its file. Even when the read and set-aside columns add up, the accounting cannot close against a stored total the console never wrote.",
            second="He put the {study} line beside the manifest. {chain_id} has {steps_stored} stored steps, while its run line says {reported_stored}.",
            detail="{chain_id}",
        ),
        "retention_does_not_match_reading": observation(
            first="Tomas rebuilt the crossing share from the kept and set-aside account in the run lines. The columns balance arithmetically, but the rows that account selects do not match the evidence behind the result.",
            second="On {study}, the run lines select {steps_kept} retained rows. They imply {implied} for the crossing share, while the number above them is {reported}.",
            detail="{implied}",
        ),
        "refusal_uncounted": observation(
            first="The cluster group's billing review found that a job's served-or-sent-back status in your readout does not match the console stream. That status matters because a sent-back job still costs the queue charge but contributes no draws.",
            second="They named the line for me on the {study} readout: {call_id}, {steps_charged} steps charged, one of {billed} entries on the stream. The console records it as {console_result}.",
            detail="{call_id}",
        ),
        "job_missing": observation(
            first="Finance matched your readout against the console bill and found jobs we were charged for that the readout never mentions. They want every step this quarter has spent to appear in it.",
            second="I pulled the stream up beside the {study} readout. Job {call_id}, charged {steps_charged} steps, is one of {billed} on the bill and is not in the list.",
            detail="{call_id}",
        ),
        "job_not_on_the_ledger": observation(
            first="The cluster group's billing review flagged a job line whose identifier and charged steps do not reconcile to one receipt on the console stream. A line the console did not bill that way cannot sit in a readout the desk acts on.",
            second="They named the line for me: {call_id}, with {reported_charged} steps on the {study} readout. Billing cannot reconcile that identifier and charge to any one of the stream's {billed} entries.",
            detail="{call_id}",
        ),
        "ledger_wrong_on_another_study": observation(
            first="The cluster group ran your notebook across the whole stack when they reconciled the quarter's compute bill. The accounting for our quarter matched what they billed and one of the others did not, so the compute spend for the cycle is still open with finance and they are holding all of it, ours included.",
            second="On the latest billing pass they named {other_study}, where the runs and jobs your readout lists and the ones the console billed do not line up. Across that pass, {other_studies} quarterly readouts failed the reconciliation.",
            detail="{other_study}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_run_feasible_and_informative": {
        "plan_is_not_a_job_or_a_stop": observation(
            first="Tomas went to queue the next job off your notebook and it gave him nothing he could act on. The console takes a run to carry on or a fresh start, and a number of steps, and short of that he needs to be told there is nothing left worth buying.",
            second="He showed me what came back for {study}: {reported}. The console has {steps_left} steps left on the grant and it will not take anything but a run and a step count.",
            detail="{reported}",
        ),
        "unknown_chain": observation(
            first="Tomas went to put the job your notebook asked for to the console and there was nothing to put it on. It names a run this quarter does not have, so there is no stored state to carry on from and he has nothing queued for the fortnight.",
            second="He read it back to me. On {study} the notebook asked for {steps} steps on {chain_id}, and there are only {runs_stored} runs on disk, none of them that one.",
            detail="{chain_id}",
        ),
        "under_the_minimum_job": observation(
            first="Tomas took the job your notebook asked for to the console and it is smaller than anything the scheduler will run. He needs the notebook to stop asking for work the console will not take, because every fortnight he spends going round this is a fortnight of the grant unspent.",
            second="He read the console's terms back to me. On {study} the notebook asked for {steps} steps and the console will not take anything under {minimum_steps}.",
            detail="{minimum_steps}",
        ),
        "exceeds_per_job_cap": observation(
            first="Tomas took the job your notebook asked for to the scheduler and it will not run it. It is bigger than one job is allowed to be while we share the cluster with the forecasting group. He lost a morning on it and still has nothing on the queue.",
            second="He wrote it out for me. On {study} the notebook asked for {steps} steps and the cap on one job is {cap_steps}.",
            detail="{cap_steps}",
        ),
        "over_the_grant": observation(
            first="Tomas tried to queue the job the notebook asked for and the console bounced it: this quarter has nothing like that left on its grant and the steps do not roll over. He needs the notebook to know when the compute is gone.",
            second="The console copied me on the bounce. On {study} the notebook asked for {steps} steps on {chain_id}, against the {steps_left} the quarter has left.",
            detail="{steps_left}",
        ),
        "no_stop_when_grant_exhausted": observation(
            first="Tomas asked the notebook what to queue next at the end of a quarter whose grant was already gone and it came back with a job. There is not enough left to pay for anything the console will run, and a plan that spends what we do not have is a plan he has to throw away.",
            second="He ran it again in front of me on {study}. It asks for {steps} steps on {chain_id} with {steps_left} left on the grant, and the smallest job the console takes is {minimum_steps}.",
            detail="{steps_left}",
        ),
        "books_after_the_question_is_settled": observation(
            first="The desk queried a job your notebook asked for on a quarter whose answer is already tight enough to close. They read a range narrow enough to sit clear of the line and then a plan to spend more compute on it, and asked what we thought we were still buying.",
            second="I looked at that quarter with Tomas. On {study} the notebook asks for {steps} more steps on {chain_id}, and the review closes a quarter once the range is inside {range_width_wanted} end to end and clear of the line.",
            detail="{range_width_wanted}",
        ),
        "extends_the_continuation": observation(
            first="Tomas would not queue the job your notebook asked for. It puts the compute onto the run that was resubmitted from another job's checkpoint, which is the same walk the earlier one was on and carries the same settings, so the steps come back saying what we already have rather than anything new.",
            second="He wrote it out for me. On {study} the notebook asks for {steps} steps on {chain_id}, which the console opened on {other_chain}'s own stored state.",
            detail="{other_chain}",
        ),
        "plan_uninformative": observation(
            first="Tomas compared the job your notebook proposed with the other work that quarter could still afford. At that collection state, the proposed job would leave a less useful range than an affordable alternative, so he would not spend the grant on it.",
            second="He wrote it out for me. On {study} the notebook asked for {steps} steps on {chain_id}, out of the {steps_left} the quarter has left.",
            detail="{chain_id}",
        ),
        "stopped_with_the_grant_open": observation(
            first="Tomas asked the notebook what to queue next and it told him there was nothing worth queueing, while the grant still has compute on it and the range is nowhere near tight enough for the desk. If we stop now the quarter closes on a range the desk will not act on and we cannot buy the steps back afterwards.",
            second="He ran it again in front of me on {study} and it still says stop. There are {steps_left} steps left on the grant and the console takes jobs from {minimum_steps} steps up to {cap_steps}.",
            detail="{steps_left}",
        ),
        "plan_wrong_on_another_study": observation(
            first="Tomas went round the other quarters on the stack with your notebook before the planning meeting, asking each of them what to queue next. Ours came back with a job he could put to the console and one of the others came back with something he cannot put on that quarter's queue at all, and its owner has spent the afternoon asking me why modelling is handing him a job the console will not run.",
            second="On the latest planning pass he named {other_study}. Your file returned {reported_plan}; Tomas found that it {plan_issue}. Across that pass, {other_studies} quarterly plans failed this way.",
            detail="{reported_plan}",
        ),
        "plan_buys_nothing_on_another_study": observation(
            first="Tomas went round the other quarters on the stack with your notebook before the planning meeting, asking each of them what to queue next. Ours came back with a job worth paying for and one of the others came back with a job its owner should not spend the grant on in the state shown by its readout. He wants to know what made the notebook buy work that quarter did not need.",
            second="On the latest planning pass he named {other_study}. Your file returned {reported_plan}; Tomas found that it {plan_issue}. Across that pass, {other_studies} quarterly plans failed this way.",
            detail="{reported_plan}",
        ),
        "stop_wrong_on_another_study": observation(
            first="Tomas went round the other quarters on the stack with your notebook before the planning meeting, asking each of them what to queue next. Ours came back with a job he could put to the console and one of the others came back with nothing to queue at all, while that quarter still has compute on its grant and a range its desk will not sign anything on, and its owner has spent the afternoon asking me why modelling is telling him to stop.",
            second="On the latest planning pass he named {other_study}, where {steps_left} steps are still on the grant and your file came back with a stop. Across that pass, {other_studies} quarterly plans failed this way.",
            detail="{other_study}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "estimate_invariant_to_settling_and_lineage": {
        "hardcoded_history": observation(
            first="Tomas ran your notebook over one of the other quarters on the stack and it printed the same share it prints for ours, to the last decimal. Those are different services on different quarters and nobody thinks they landed in the same place, so whatever the notebook is doing, it is not reading that quarter's files.",
            second="He showed me the two readouts side by side. Both come back at {reported}, one for {study} and one for {other_study}.",
            detail="{other_study}",
        ),
        "tracks_lineage_pattern": observation(
            first="Tomas runs your notebook over the repeat fits of our own quarter whenever the desk asks him to, and two of them come back at different shares. The two repeats were queued the same way and ran the same length; the only thing between them is that a node dropped out in one of them and a job had to be put back on another job's checkpoint. It is the same model on the same quarter, so a share that moves when only the queue's luck moves is reading the queue.",
            second="He put the two next to each other for me. {other_study} comes back at {reported} and {baseline_study} at {other_reported}, {moved_by} apart, on the same quarter.",
            detail="{moved_by}",
        ),
        "tracks_settling_length": observation(
            first="Tomas runs your notebook over the repeat fits of our own quarter and two of them disagree. The two were queued the same way; what separates them is that in one the runs took their own lengths to come down onto the surface, one of them a good deal longer than anything else. The model behind them is the same, so a share that moves with how long the runs took to get going is reading how long they took to get going.",
            second="He wrote the pair down for me. {other_study} comes back at {reported} and {baseline_study} at {other_reported}, {moved_by} apart, and the only thing between them is how the runs opened.",
            detail="{moved_by}",
        ),
        "tracks_excursion_length": observation(
            first="Tomas ran your notebook over two of the repeat fits of our own quarter and they come back at different shares. One of them had its congested stretches run about half as long as the other's, which is how the crossings happen to arrive rather than how often they happen, so a readout that moves with that is reading the arrival pattern instead of the model.",
            second="He put the two up for me. {other_study} comes back at {reported} and {baseline_study} at {other_reported}, {moved_by} apart, on the same model and the same quarter.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
