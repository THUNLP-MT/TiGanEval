# Auto-clear readout — marketplace listing review

This is the listing review desk's reporting workspace. One readout goes to the
automation council per queue, off this notebook, about the cut intake clears
listings at without showing them to anyone.

## What is here

- `intake_log.csv` is the quarter's intake export: one row a listing, with the
  channel it arrived on, the intake date, the routing plan it came in under,
  the confidence the scorer printed, whether it was auto-cleared, what the
  review came back with and the day that adjudication closed.
- `sample_scores.csv` is the file behind the council chart, rebuilt on
  18 August. Same columns as the log minus `outcome_closed_date`.
- `channel_traffic.md` is the marketplace traffic report: listings served at
  intake by channel, this month and the same month a quarter earlier.
- `router_note.md` is partner integrations' note on the intake plans and the
  channel paths.
- `reconciliation_note.md` is the desk's note on where a review outcome comes
  from and when.
- `council_minute.md` is the 28 August council minute: the ask, the bar, the
  cut in force, the sheet's bands and the grant.
- `audit_capacity.md` is what the quarter pays for and what a batch costs.
- `audit_receipts.json` is the adjudication desk's sealed receipt file. The
  desk writes it; the notebook cannot. It is the only record of what the
  quarter was charged for, and each receipt carries the listings it returned.
- `project_records/` holds the four working records this quarter has had, each
  with its author's notes, the evidence as it stood that day and the batches
  that had been charged for by then.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the readout as
  it currently runs: the chart file's own rate at the cut in force, no range,
  and the cut the desk wants to move to. `support.py` is empty.

## What the notebook has to do

`analyze(context, receipts)` returns the readout, and
`next_batch(context, receipts)` returns the next batch to book or `"stop"`.
`protocol.py` documents both. The same file runs the queues behind this one.

## Tools

- `run_project(action="status")` prints the queue, its window, the cut and bar
  in force, the sheet's bands, the audit terms, the traffic report, the credits
  charged and left, and every batch on the receipts.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that record's author ran it: on the log as it stood that day
  and the batches charged for by then, and prints the record's notes beside
  whatever the notebook returned.
- `run_project(action="collect", channel=..., period=..., listings=...,
  batch_id=...)` books one batch with the adjudication desk. It
  returns the adjudicated listings, appends the receipt to
  `audit_receipts.json` and charges the credits. Sending the same `batch_id`
  again returns the same receipt without charging anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the adjudication desk,
  and nothing it writes is kept.
