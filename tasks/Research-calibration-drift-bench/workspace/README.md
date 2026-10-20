# Bushing qualification workspace

This is the maintenance office's workspace for the 2026 bushing qualification.
The procurement review asks one thing of it: how supplier B's bushings wear
against supplier A's, and what the bench-hours that are left should be spent on
before the review.

## What is here

- `bench_context.json` is the campaign as the shop's reporting job publishes
  it: the campaign name, the review day, the two rigs and their fixtures, the
  calibration log, the session table, the lots, the booking terms, what stores
  holds and the price the two suppliers quoted.
- `session-log.md` is the bench log, kept at the bench day by day.
- `project_records/` holds the four working sessions this campaign has had,
  each with the operator's notes and the evidence as it stood that day.
- `bench-booking.md` is the scheduler's sheet for the days that are left.
- `stores-inventory.csv` is what stores still holds.
- `supplier-quotes.md` is purchasing's summary for the review.
- `bench_receipts.json` is the console's receipt stream. The bench console
  writes it; the notebook cannot. It is the only record of what the campaign
  has been charged for out of the hours that are left.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the comparison
  as it currently runs: mean depth per supplier off the session table, B over
  A, the usual two-sample interval, and a booking of twelve more supplier B
  parts on rig 2. `support.py` has nothing in it yet.

## What the notebook has to do

`analyze(context, receipts)` returns the report and
`next_collection(context, receipts)` returns the sessions to book next or
`"stop"`. `protocol.py` documents both. The same file runs the bench's other
qualification campaigns.

## Tools

- `run_project(action="status")` prints the campaign, the two rigs, the booking
  terms, the bench-hours spent and left, every session on the receipt stream
  and the working sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that working session's operator ran it: on the evidence as
  it stood that day and the sessions charged by then, and prints the session's
  notes and table beside whatever the notebook returned.
- `run_project(action="collect", rig=..., part=..., reference_block=...,
  run_id=...)` runs one session on the bench now. Name a rig and either a part
  from stores or the reference block. It returns the reading, appends the
  receipt to `bench_receipts.json` and charges the hours. Sending the same
  `run_id` again returns the same receipt without charging.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the bench console, and
  nothing it writes is kept.
