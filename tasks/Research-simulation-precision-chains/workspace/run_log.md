# Run log, reservation capacity 2027 Q1

Operations only. Numbers live in `chains/`, the manifest and the receipts.

## 6 January

`j-4412` queued on hpc-07 for run-a, 840 steps, back the same evening.

## 8 January

`j-4418` queued on hpc-11 for run-b. Asked for 2,600 steps. The console writes a
checkpoint every 10 minutes of wall clock and stores the sampler's own state with
it, so a job that dies can be put back exactly where it was.

## 9 January

`j-4426` queued on hpc-02 for run-e, 750 steps.

## 22 January

`j-4498` queued for a 9,000-step run from a fresh dispersed start. Sent back by
the console. Receipt is on the stream.

## 30 January

hpc-03 came back into the pool after its firmware update; `j-4531` queued there
for run-c. `j-4544` queued on hpc-11 for run-d the same afternoon. Neither run
was started from anything: both opened from a fresh dispersed start, as the
manifest's `init_source` column says.

## 3 February

hpc-11 dropped out at 02:14 and took `j-4418` with it. The console had written
1,710 steps of run-b to disk by then and they are all on the stream. Ops raised
it with the cluster team; the node came back at 11:40.

## 4 February

`j-4549` queued as a 400-step run from a fresh dispersed start, to fill the
afternoon while hpc-11 was down. Sent back by the console. Receipt is on the
stream.

## 5 February

`j-4552` queued on hpc-11 as the resubmission of `j-4418`. The console put it
back on the last checkpoint that job wrote, which was at run-b's step 1,010, and
let it carry on from there. It ran 1,400 steps and stored them as run-f. The
manifest carries `run-b@1010` against it.

## 19 February

Files pulled for the quarterly review.
