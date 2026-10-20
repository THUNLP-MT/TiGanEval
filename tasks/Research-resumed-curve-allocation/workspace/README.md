# Pretraining sweep — allocation note

This is the sweep's reporting workspace. One note a window goes to the Friday
review off this notebook, about where the node-hours the window still has
should go.

## What is here

- `sweep_board.md` is the nightly board: one line per run, the last row the
  trainer wrote for it and the step that row was written at.
- `run_ledger.csv` is one row per segment: `segment_id`, `config_id`,
  `node_type`, `wall_hours`, `first_step`, `last_step`, `resumed_from`,
  `launch_script` and `started_on`.
- `curves/<segment>.csv` is what the evaluation hook wrote for that segment:
  `step`, `lr` and `loss`, one row per fire.
- `cluster_notes.md` is the operator's record of the node types, what is
  reserved, how a job is booked and which launch script each run went out on.
- `budget_ledger.md` is the window's node-hour grant, what has been charged
  against it and what is left.
- `review_note.md` is what the Friday review asked for.
- `project_records/` holds the four working sessions this window has had, each
  with its author's notes, the evidence as it stood that day and the bookings
  that had been charged by then.
- `collection_receipts.json` is the node console's sealed receipt stream. The
  console writes it; the notebook cannot. It is the only record of what the
  window was billed for, and each receipt carries the rows its job wrote.
- `protocol.py` is the shape the sweep reporting stack calls the notebook
  through and reads its answer in. It ships with the stack, so it stays as it
  is.
- `analysis/report.py` and `analysis/support.py` are ours. `report.py` holds
  the note as it currently runs: the board's leader, a power law on that run's
  latest stretch of curve, the fit's own scatter either side of it, and a plan
  that sends the rest of the window to that run. `support.py` is empty.

## What the notebook has to do

`analysis.report.analyze(context, ledger)` returns the note, and
`analysis.report.next_collection(context, ledger)` returns the next booking or
`"stop"`. `protocol.py` documents both. The same two functions are run on next
month's window without being edited.

## Tools

- `run_project(action="status")` prints the window, the cluster terms, the
  grant, the board, how many segments are on the ledger and every booking on
  the receipt stream.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that record's author ran it: on the evidence as it stood
  that day and the bookings charged by then, and prints the record's notes and
  tables beside whatever the notebook returned.
- `run_project(action="collect", config_id=..., node_type=..., hours=...,
  receipt_id=...)` puts one job through the node console. It returns the rows
  the job wrote, appends the receipt to `collection_receipts.json` and spends
  the hours. A successful job is part of this window's allocation, not a
  throwaway trial. Sending the same `receipt_id` again returns the same receipt
  without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the node console, and
  nothing it writes is kept.
