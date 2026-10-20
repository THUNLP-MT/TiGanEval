# Reservation capacity 2027 Q1

Capacity modelling. Everything the quarterly readout runs on is in here, with the
charter the platform group and the commitments desk signed, the compute grant's
terms, the run log and the notes from each working session this quarter has had.

## What is here

- `chains/<chain_id>.csv` is one stored run, one row per sampler step, numbered
  from 1: the two model coordinates the console writes (`arrival_rate`,
  `service_rate`), the quarter's `peak_wait_s` implied by that step, the
  sampler's `step_size` at that step, and whether the step was `accepted`.
- `chain_manifest.csv` is one row per stored run: its `chain_id`, the `node` it
  ran on, the console `job_id`, the `steps_stored` in its file, and the
  `init_source` the console opened it at — either a dispersed start or another
  run and the stored step it was put back on.
- `collection_receipts.json` is the console's own receipt stream: one entry per
  job, served or refused, with the steps it asked for, returned and charged. What
  this quarter has been billed for is in there and nowhere else.
- `capacity_charter.md` is the commitment the platform signed and what the review
  asks the modelling group for, with the minute the commitments desk keeps on the
  file.
- `compute_ledger.md` is the grant, what had been spent at the last accounting,
  the cap on one job, the smallest job the console will take and what a refused
  job costs.
- `run_log.md` is operations: what was queued where, what came back, what fell
  over.
- `session_notes.md` is what the readout has printed at each working session.
- `project_records/` holds the four working sessions this quarter has had, each
  with the analyst's notes and the files as they stood that day.
- `protocol.py` travels with the capacity reporting stack: it is how the stack
  calls a notebook and how it reads the answer back, so it is not ours to change.
- The two files this group owns are `analysis.py` and `support.py`.
  `analysis.py` is the readout as it runs today: the average peak wait over every
  stored draw, how far that average could move, and a plan that asks the
  console for more runs from scratch. `support.py` has nothing in it yet.

## What the stack expects back

`analyze(context, receipts)` returns the readout and
`next_run(context, receipts)` returns the next job to put to the console, or
`"stop"`. `protocol.py` documents both. The same file produces the readouts for
the other quarters on this stack.

## Tools

- `run_project(action="status")` prints the study, the charter's terms, the
  compute steps charged and left, every job on the receipt stream, a per-run
  summary of the stored files, and the working sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's analyst ran it — the files as they stood on the
  day, the jobs billed by then — and prints the session's notes, that day's
  per-run summary and whatever the notebook handed back.
- `run_project(action="collect", chain_id=..., steps=..., call_id=...)` puts one
  job to the console to carry a stored run on; `start_new=true` instead of a
  `chain_id` opens a run from a fresh dispersed start. It returns the steps the
  console ran, writes them onto that run's file in `chains/`, updates
  `chain_manifest.csv`, appends the receipt to `collection_receipts.json` and
  charges the grant. Sending the same `call_id` again returns the same receipt
  without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the console, and nothing it
  writes is kept.
