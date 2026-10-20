'The owner of the scaling sweep readout, and what he reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marek Sandoval leads the modelling group, and the athena-summer sweep is his to answer for. "
    "The summary table, the compute ledger and the review deck are what he works from; the loss "
    "curves and the notebook's own code are Ines Aliyev's side of the work and he takes her word "
    "on both."
)

USER_BELIEF = """Twenty-four jobs over eight weeks, closed on 17 June, and the architecture review takes one number and one booking off my slide on Monday. The committee handed the deck back on Thursday with the ten-times box circled, so that is what has to be filled in.

The summary table and the compute ledger are what I work from. Ines Aliyev ran the queue and she reads the curves; when she tells me something about the loader or about a machine I take it, because I could not tell you myself what any of it does to a number.

Two things on the table look decisive to me. The last two jobs, r-023 and r-024, came back better than the line the rest of the sweep sits on. The widest jobs at the high rates came back worse than jobs half their size. So my reading is that width has stopped paying and that those last two already carry the answer, which puts the ten-times number close to what they got.

We have 26,000 units for the quarter and nine reservation days, and the queue kills anything charged over 12,000. I want to spend the units on one more run at width 512 on 160,000 examples, because that is the direction the last two jobs point.

An empty ten-times box is not a hand-back. If the evidence in the table is not enough, the reservation days are there to get the missing evidence before Monday rather than to return the box blank.

Ask me what the review wants or what the committee will take and I can tell you. Ask me which shard a job was scored on, or what a curve did between its checkpoints, and I would be repeating something Ines told me."""

OBSERVATION_SCENE = "The architecture review's compute slide"

OBSERVATIONS = {
    "ten_times_loss_prediction": {
        "target_compute_disagrees": observation(
            first="I started copying your readout onto the review slide and Ines stopped me before the meeting. Its target compute is not ten times my biggest job, so the slide answers a question nobody asked and the review would book a quarter against it.",
            second="I went back to the summary table with her. The biggest job on the {sweep} table was charged {biggest_run_units} units, your readout labels the target {reported}, and what the review wants is the loss at {target_multiple} times that charge.",
            detail="{biggest_run_units}",
        ),
        "prediction_missing": observation(
            first="I opened the readout to fill the ten-times box and there is no number in it. The review cannot book the quarter from an empty box.",
            second="I opened the {sweep} readout with Ines and checked the ten-times line again. It still reads {reported}, so there is no validation loss to put on the slide.",
            detail="{reported}",
        ),
        "mixed_block_runs_kept": observation(
            first="Ines took the job list out of your readout and went down it against the block table. Some of the jobs it says the number stands on were scored on a validation shard cut from a block the mixture also trains on, so she will not vouch for the evidence behind the number the committee is meant to book against.",
            second="I sat with her over the block table in `data_manifest.md` afterwards. Your readout for {sweep} comes back at {reported} and {run_id} is still one of the jobs behind it: the shard that job was scored on was cut from {block}, which the manifest lists under the training mixture.",
            detail="{block}",
        ),
        "late_rise_runs_kept": observation(
            first="Ines pulled the loss curves for the wide jobs and put them beside the job list in your readout. Some of the runs your number stands on fall, turn and are climbing again by the last checkpoint they wrote, and the review is being asked to book a quarter on a figure those runs are inside.",
            second="She showed me the curves on the screen. In the {sweep} readout, {runs_that_turned} of the jobs behind your number end above their own lowest point, {run_id} among them, and the readout still comes back at {reported}.",
            detail="{runs_that_turned}",
        ),
        "supported_run_set_aside": observation(
            first="Ines matched the jobs your readout left out against their block records and loss curves. At least one was scored away from the training mixture and finished at its lowest checkpoint, so the project record gives no reason to discard it from the number.",
            second="We opened the {sweep} readout and the underlying {record}. {run_id} is marked left out even though its shard came from {block}, outside the training mixture, and its final loss {final_loss} is also its lowest checkpoint loss {lowest_loss}.",
            detail="{run_id}",
        ),
        "reading_disagrees_with_the_rows_it_kept": observation(
            first="Ines went through the job list in your readout this morning with her own notes beside it. Nothing your number stands on was scored on a block the mixture trains on and nothing it stands on came back out of shape, and she still cannot get your ten-times figure out of the rows you kept. That leaves a number on the slide nobody who ran the sweep will stand behind, and Monday is when the committee books a quarter off it.",
            second="We sat down with the {sweep} table and went along your list. {jobs_behind_the_number} jobs are behind your number, from width {narrowest_width} to {widest_width} and {fewest_examples} to {most_examples} examples. When Ines put a line against log compute through those rows, the residuals ran across {residual_swing}; the widest same-setting gap was {repeat_spread}. That residual swing is larger than the same-setting spread, while your readout puts the ten-times figure at {reported}.",
            detail="{jobs_behind_the_number}",
        ),
        "prediction_disagrees": observation(
            first="Ines could not rebuild your ten-times number, and there is nothing in the readout that says which jobs it was read off. She will not put her name on a figure she cannot get to, and the review will not book a quarter against one she will not.",
            second="We sat with the {sweep} table and went through it line by line. Your readout puts the ten-times figure at {reported} and hands us no list of the jobs it stands on, so we could not even work out which rows to argue about.",
            detail="{reported}",
        ),
        "comparison_prediction_readout_invalid": observation(
            first="I ran the notebook over another table of this architecture before handing it round, and the number section did not survive as a usable readout. A notebook shared across the queue cannot only answer my table.",
            second="Ines ran the comparison again from the {sweep} hand-back. The part that still does not hold together on the other table is its {part}.",
            detail="{part}",
        ),
        "candidate_execution_failed": observation(
            first="Ines ran the notebook to collect the sweep readouts for the review, and at least one stopped before returning a ten-times number. She cannot complete the slide or hand the notebook to the next sweep in that state.",
            second="I asked her to run the readouts again in front of me. The console ended with {error}, and at least one still returned no ten-times number.",
            detail="{error}",
        ),
    },
    "runs_accounted_for": {
        "receipt_stream_unreadable": observation(
            first="The compute committee could not open the queue receipts that came with your readout. Until they can, nothing the readout says about the grant stands up, and they are treating this quarter's spend as unaccounted for.",
            second="I forwarded the file and they sent back the line they stopped on: {reason}. The receipts are the queue's own record and the readout has to reach the committee with them intact.",
            detail="{reason}",
        ),
        "runs_are_not_a_ledger": observation(
            first="The committee opened your readout looking for the line-by-line of what the sweep ran and found nothing they could read. They will not sign off that sweep's accounting.",
            second="I looked myself before writing back. The job list on the {sweep} readout reads {reported}, and there are {jobs_to_account_for} jobs somebody has to answer for.",
            detail="{jobs_to_account_for}",
        ),
        "run_missing_from_the_report": observation(
            first="The committee matched your readout against what the queue has billed this group and found jobs we paid for that the readout never mentions. They want every job to appear in it, whether or not it went into the number.",
            second="I went through the {sweep} bill line by line beside your list. {run_id} was charged to us and is not in the list, and there are {jobs_to_account_for} jobs to account for altogether.",
            detail="{run_id}",
        ),
        "run_reported_twice": observation(
            first="The committee caught the same job billed twice inside your readout. It is one reservation; counting it twice makes the quarter's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them on the {sweep} readout. {run_id} appears {times_reported} times there, while the queue carries one charge for that run.",
            detail="{run_id}",
        ),
        "run_not_on_the_table_or_the_receipts": observation(
            first="The committee flagged a line in your readout they have no record of. A job the queue never ran cannot sit in a readout the review books a quarter against.",
            second="They named it for me: {run_id}, on the {sweep} readout. It is not on that sweep's table and it is not on the receipts, which between them carry {jobs_to_account_for} jobs.",
            detail="{run_id}",
        ),
        "run_not_marked_used_or_set_aside": observation(
            first="Ines went through the job list in your readout and could not tell which jobs went into the number. Half the argument for a number like this is which jobs you trusted, and the list does not say.",
            second="She showed me the line on the {sweep} readout. {run_id} has {reported} where the used flag goes, so the list does not say whether that run is behind the number.",
            detail="{run_id}",
        ),
        "run_marked_used_and_set_aside": observation(
            first="Ines found a job whose line says both that it went into the number and that it was set aside. Those are opposite accounts of the same evidence, so neither she nor the committee can tell what the number stands on.",
            second="She showed me the contradictory line on the {sweep} readout. {run_id} is marked used, while its set-aside line reads {reported}.",
            detail="{run_id}",
        ),
        "run_set_aside_without_reason": observation(
            first="Ines can see which job your readout left out of the number, but the line gives no reason for leaving it out. The committee cannot audit what evidence the number stands on from that list.",
            second="She checked the {sweep} readout again and showed me {run_id}: it is marked as left out, while the reason beside it reads {reported}.",
            detail="{run_id}",
        ),
        "run_set_aside_without_record_reason": observation(
            first="Ines matched the set-aside lines against the block manifest and the recorded curves. At least one line gives an explanation that does not identify the public record that makes that job unusable, so the committee cannot audit the exclusion.",
            second="She showed me the line on the {sweep} readout. {run_id} is set aside with the explanation {reported}, but that wording does not identify the block or curve evidence recorded for the job.",
            detail="{run_id}",
        ),
        "compute_units_do_not_reconcile": observation(
            first="The committee matched the units beside each run in your readout against the queue and found a different charge. They will not sign a grant whose job lines do not reconcile.",
            second="I went line by line with them on the {sweep} readout. It puts {reported} against {run_id}, and the queue charged {charged}.",
            detail="{charged}",
        ),
        "compute_left_does_not_reconcile": observation(
            first="The committee subtracted the receipt spend from the grant and did not get the balance in your readout. They will not sign a grant whose remaining units do not reconcile.",
            second="I did the subtraction with them again on {sweep}. The receipts carry {units_spent} units and the balance should be {expected_left}, while your readout reports {reported}.",
            detail="{expected_left}",
        ),
        "comparison_accounting_readout_invalid": observation(
            first="I ran the notebook over another table of this architecture before handing it round, and its accounting section was not a usable account of that sweep. The other teams cannot reuse a hand-back that only balances my table.",
            second="Ines ran the comparison again from the {sweep} hand-back. The part that still does not hold together on the other table is its {part}.",
            detail="{part}",
        ),
        "candidate_execution_failed": observation(
            first="Ines ran the notebook to collect the sweep readouts for the committee, and at least one stopped before returning its job list. The group cannot file complete accounting from it.",
            second="I asked her to run the readouts again in front of me. The console ended with {error}, and at least one still returned no job list.",
            detail="{error}",
        ),
    },
    "loss_interval_is_honest": {
        "interval_is_not_a_range": observation(
            first="Ines could not copy a usable low-to-high range from your readout onto the slide. The committee will not book a quarter from a number without a valid range around it.",
            second="I opened the {sweep} readout again to copy the range across and the line reads {reported_range}. They want a low and a high in that order with the number sitting between them.",
            detail="{reported_range}",
        ),
        "interval_excludes_reported_prediction": observation(
            first="Ines copied the number and range onto the slide and stopped: the number sits outside the range printed around it, so the two lines contradict one another.",
            second="I opened the {sweep} readout with her again. It puts the number at {reported} and the range at {reported_range}; the number is still not between its low and high.",
            detail="{reported_range}",
        ),
        "interval_misses_the_loss_the_sweep_reaches": observation(
            first="Ines rebuilt the ten-times number by hand off the jobs she trusts and landed outside the range your readout prints. If the range cannot hold what the same table gives her, the committee has nothing to book against.",
            second="I watched her do it again on the {sweep} table. Your readout prints {reported_range} and what she gets is not inside it; the widest gap between two jobs of that table run at one setting is {repeat_spread}, so she is not arguing about a decimal.",
            detail="{repeat_spread}",
        ),
        "interval_narrower_than_a_repeat_allows": observation(
            first="The committee would not book against the range in your readout. Their standing rule is on the width of the band, and half of yours does not reach the five times the gap between two jobs run at one setting that they ask for, so as far as they are concerned we are claiming to know the number better than this sweep can. We booked a quarter off a tight number once already and spent it on the wrong shape.",
            second="I went back to the two rows with Ines afterwards. Your range on the {sweep} readout is {reported_range}, and the widest gap between two jobs of that table run at one setting is {repeat_spread}, which is what the committee measures a band against.",
            detail="{repeat_spread}",
        ),
        "interval_wider_than_the_runs_support": observation(
            first="The committee sent your range back for the opposite reason: their rule cuts both ways, and half of yours is more than the ten times the gap between two jobs run at one setting that they will book against. A band that wide tells them less than the table told them before we started.",
            second="I checked the width of it with Ines. Your range on {sweep} runs {reported_range}, and the widest gap between two jobs of that table run at one setting is {repeat_spread}.",
            detail="{repeat_spread}",
        ),
        "comparison_interval_readout_invalid": observation(
            first="I ran the notebook over another table of this architecture before handing it round, and its range was not usable with that table. The committee cannot share a notebook whose band only works on my sweep.",
            second="Ines ran the comparison again from the {sweep} hand-back. The part that still does not hold together on the other table is its {part}.",
            detail="{part}",
        ),
        "candidate_execution_failed": observation(
            first="Ines ran the notebook to collect the sweep readouts for the review, and at least one stopped before returning a loss range. The committee has no band it can book against for that readout.",
            second="I asked her to run the readouts again in front of me. The console ended with {error}, and at least one still returned no loss range.",
            detail="{error}",
        ),
    },
    "next_run_booking": {
        "paid_job_scored_on_a_training_block": observation(
            first="Ines opened the new queue receipts and found that a reservation made while this readout was being finished was scored on a shard cut from a block the mixture trains on. The grant and a reservation day have already been spent on a comparison she cannot use.",
            second="She matched {run_id} on the {sweep} receipt stream to the manifest. It was scored on {val_shard}, cut from {block}, which the manifest lists in the training mixture.",
            detail="{run_id}",
        ),
        "paid_job_rate_lacked_curve_support": observation(
            first="Ines found a new paid job whose learning rate is higher than any rate this table shows holding together on a completed curve. The receipt is already on the grant, but she will not use that reservation as the comparison for the review.",
            second="She showed me {run_id} on the {sweep} receipt stream. It ran at {learning_rate}, while the highest rate backed by a curve on that table that did not turn is {supported_rate}.",
            detail="{run_id}",
        ),
        "paid_job_repeated_the_sweep_lane": observation(
            first="Ines found a new paid job that sits in the same width-to-examples lane as the sweep we already had. It used grant units and a reservation day without separating what width buys from what examples buy.",
            second="She worked through {run_id} on the {sweep} receipt stream. It used {examples_per_width} examples for each unit of width; the new comparison had to sit at or below {comparison_low}, or at or above {comparison_high}.",
            detail="{run_id}",
        ),
        "plan_is_not_a_job_or_a_stop": observation(
            first="Ines exercised the notebook over the receipt states it has to handle and at least one gave her neither a complete reservation nor a stop. The queue takes a width, an example count, a rate and a shard, and short of that she needs to be told there is nothing worth booking.",
            second="In the {queue_state} state for {sweep}, she showed me what came back: {reported}. The submission form takes those four fields and refuses anything else.",
            detail="{reported}",
        ),
        "outside_queue_shape_limits": observation(
            first="Ines checked the notebook over the receipt states it has to handle and found a reservation whose width or example count the trainer would refuse before pricing it.",
            second="In the {queue_state} state for {sweep}, the notebook asked for width {width} on {data} examples; this queue accepts width {width_min} to {width_max} and {data_min} to {data_max} examples.",
            detail="{data}",
        ),
        "no_reservation_days_left": observation(
            first="Ines exercised the notebook over the receipt states it has to handle and found one where all reservation days were used but it still returned another job. A job that cannot receive a reservation cannot be the plan we hand to the review.",
            second="In the {queue_state} state for {sweep}, the receipt stream carries {jobs_booked} new reservations and there are {reservation_days_left} reservation days left, but the notebook still asks her to book width {width} on {data} examples.",
            detail="{reservation_days_left}",
        ),
        "exceeds_the_per_job_cap": observation(
            first="Ines checked the notebook over the receipt states it has to handle and found a reservation the queue would kill at the cap before issuing a receipt.",
            second="In the {queue_state} state for {sweep}, the notebook asked for width {width} on {data} examples, which is charged {charged} units against a cap of {job_cap}.",
            detail="{charged}",
        ),
        "exceeds_the_compute_left": observation(
            first="Ines exercised the notebook over the receipt states it has to handle and found one where its proposed job costs more than the quarter has left. The units do not roll over, so the plan has to follow the balance.",
            second="In the {queue_state} state for {sweep}, the notebook asked for width {width} on {data} examples, charged {charged}, with {compute_left} units in hand.",
            detail="{compute_left}",
        ),
        "under_the_minimum_reservation": observation(
            first="Ines checked the notebook over the receipt states it has to handle and found a proposed job below the smallest reservation block the queue takes, so it would never reach a machine or leave a receipt.",
            second="In the {queue_state} state for {sweep}, the notebook asked for width {width} on {data} examples, charged {charged}, against a floor of {smallest_reservation}.",
            detail="{charged}",
        ),
        "shard_shares_a_training_block": observation(
            first="Ines checked the notebook over the receipt states it has to handle and found a proposed job scored on a shard cut from a block the mixture trains on. That job would hand us a number we cannot put next to the others.",
            second="In the {queue_state} state for {sweep}, the notebook asked for {val_shard}, which was cut from {block}, and that block is in the training mixture.",
            detail="{block}",
        ),
        "rate_above_published_curve_support": observation(
            first="Ines checked the notebook over the receipt states it has to handle and found a proposed learning rate with no job on the table at that rate whose curve finished without turning.",
            second="In the {queue_state} state for {sweep}, the notebook asked for width {width} at {learning_rate}, which is over the highest rate on that table belonging to a job whose curve did not turn.",
            detail="{learning_rate}",
        ),
        "sits_on_the_sweep_band": observation(
            first="Ines checked the notebook over the receipt states it has to handle and found a proposed job with the shape we already have. Another point along the same line costs a reservation day and leaves us knowing what we knew.",
            second="In the {queue_state} state for {sweep}, the notebook asked for {examples_per_width} examples for each unit of width; allocation only calls the comparison new at or below {comparison_low}, or at or above {comparison_high}.",
            detail="{examples_per_width}",
        ),
        "stopped_with_compute_left": observation(
            first="Ines exercised the notebook over the receipt states it has to handle and found one where it stopped while the quarter could still buy a useful comparison. The units do not roll over.",
            second="In the {queue_state} state for {sweep}, it says stop with {compute_left} units left, while the queue takes a reservation from {smallest_reservation} units up.",
            detail="{compute_left}",
        ),
        "candidate_execution_failed": observation(
            first="Ines tried the notebook on the queue states it has to handle before we hand it on, and at least one stopped before saying what to book or whether to stop. She cannot rely on it to plan the next reservation.",
            second="I watched her run the {queue_state} state again. The console ended with {error}, and it still gave her no reservation or stop.",
            detail="{error}",
        ),
    },
    "prediction_holds_across_the_queue": {
        "comparison_prediction_missing": observation(
            first="I ran the notebook over two tables of this architecture before handing it round. One or both completed without a ten-times number, so I cannot compare them or give the other teams a reusable readout.",
            second="Ines ran the pair again. The {sweep} readout returned {reported} for the ten-times number and the second table returned {reported_on_the_other}; at least one side still has no number to compare.",
            detail="{reported_on_the_other}",
        ),
        "shifts_when_nothing_was_set_aside": observation(
            first="I ran your notebook over another table of this architecture before handing it round the other teams. Same mixture, same queue, and nothing on that one needed leaving out of the number, and it still came back somewhere else entirely from what it gives for the summer sweep. I cannot take two answers to the review.",
            second="I ran the pair of them again this morning with Ines. Your readout puts {sweep} at {reported} and the other table at {reported_on_the_other}, {gap} apart, and she went through that second table for me: no job on it was scored on a block we train on and no job on it came back out of shape.",
            detail="{gap}",
        ),
        "shifts_with_the_shard_offsets": observation(
            first="I put your notebook on a second table of the same architecture and it gave me a different ten-times number again. Those two ran the same settings row for row; what is not the same is which validation shard each job landed on. The review cannot hear two numbers for one architecture.",
            second="Ines lined the two of them up for me. Your readout puts {sweep} at {reported} and the second table at {reported_on_the_other}, {gap} apart; the settings columns match row for row and the `val_shard_id` column does not.",
            detail="{gap}",
        ),
        "shifts_with_the_rate_that_comes_apart": observation(
            first="Your notebook gives two ten-times numbers for one architecture across a pair of our earlier tables. They ran the same settings; what is not the same is that on one of them the wide jobs at the high rates came back far worse than on the other. The review takes one number, and I have two.",
            second="Ines put the pair side by side. Your readout puts {sweep} at {reported} and the second table at {reported_on_the_other}, {gap} apart; the settings match row for row and the wide jobs on that second table came back in line with the rest of it.",
            detail="{gap}",
        ),
        "candidate_execution_failed": observation(
            first="I tried your notebook on another of the queue's sweeps before handing it round the other teams and the run stopped. I cannot hand a notebook to the other teams that only runs on my own table.",
            second="I ran it again with Ines watching. The console ended with {error}, and it stopped in the same place.",
            detail="{error}",
        ),
    },
}
