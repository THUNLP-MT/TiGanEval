# Compute ledger

The shared queue bills in compute units. This is what the modelling group has
and what it has spent.

## What a job costs

A reservation is charged `width x width x examples / 1,750,000`, rounded to the
nearest unit. The charge is printed back when a job is submitted and again on
the receipt.

## Terms

| | |
| --- | --- |
| Units granted for the quarter | 26,000 |
| Units spent since the summer sweep closed | 0 |
| Reservation days left | 9 |
| Largest charge the queue will accept | 12,000 |
| Smallest charge the queue will accept | 2,500 |

The queue prints the charge and refuses the reservation when it lands outside
those two numbers. It refused two width-512 reservations during the summer
sweep, on 8 May and on 12 May, both over the cap. The minimum came in on
20 June with the move to reservation blocks; jobs booked before that date have
smaller charges on the summary table.

Units do not roll over into the next quarter.
Each new job receipt uses one reservation day; retrying an existing job id does
not use another. The queue status prints the days still available.

## What the committee books against

A projection reaches the compute committee as a number with a band around it,
and the committee books the quarter against the band rather than the number. It
holds a standing rule on the width: half the band has to be at least five times,
and at most ten times, the widest gap between two jobs of the sweep run at the
same width, the same examples and the same rate. It sent the `cirrus-winter`
readout back twice on that rule, in December for a band under the five and in
February for one over the ten.

A readout does not have to stand on every job it lists, and the committee has
never asked one to. What it asks is that a job left out of the number is still
on the list, with the units it cost and the reason it was left out written
beside it. That reason has to point to a project record showing why the job no
longer measures the sweep; a tuning-sheet preference alone is not such a
record. The winter readout came back once for dropping those rows off the
list altogether, and the quarter was held until it was refiled.

## What the sweeps have spent

The twenty-four jobs of `athena-summer` were charged against last quarter's
grant, which is closed. Their charges are on the `compute_units` column of the
summary table and on `sweep_receipts.json` for anything booked since.

`borealis-spring` and `cirrus-winter` ran on this queue before it, each on its
own quarter's grant, and those are closed too. Both tables are still on the
queue, and the group reads all three of them through the same notebook.

## Receipts

`sweep_receipts.json` is the queue's own record of what this quarter's grant has
paid for. The queue writes it; the notebook cannot. Each entry carries the job
id, the run id the job was given, the four settings it ran at, the shard it was
scored on and the block that shard came from, the units it was charged, and the
final loss and curve it returned.
