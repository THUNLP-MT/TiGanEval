# Checkout hint readout

This is the analytics workspace for the September checkout-hint readout. The
release board asks one question of it: does the hint earn the rollout, and what
should we still measure before saying so.

## What is here

- `readout_context.json` is the readout as the reporting job publishes it: the
  window, the gate the release is judged against, which service serves each
  arm, the archive terms, the change log, the daily session table and the
  checkout queue counters.
- `pipeline_notes.md` is how the serving and logging path actually works, as
  platform wrote it down for us.
- `rollout_charter.md` is what the release board signed before the window
  opened, with the minute finance asked to keep on the file.
- `project_records/` holds the four working sessions this readout has had, each
  with the operator's notes, the evidence as it stood that day and the archive
  rescans that session had paid for.
- `audit_receipts.json` is the rescan receipt stream. The archive rescan
  service writes it; the notebook cannot. It is the only record of what this
  readout has been billed for.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the readout as
  it currently runs: arm totals off the session table, the usual interval, the
  call against the gate, and a plan that keeps buying treated days. `support.py`
  is empty.

## What the notebook has to do

`analyze(context, receipts)` returns the readout, and
`next_collection(context, receipts)` returns the next archive rescan to buy or
`"stop"`. `protocol.py` documents both. The same file runs the other readouts on
this stack.

## Tools

- `run_project(action="status")` prints the readout, the archive terms, how
  many rescan units are spent and left, every rescan on the receipt stream and
  the sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's operator ran it: on the evidence as it stood
  that day and the rescans that had been paid for by then, and prints the
  session's notes, its daily numbers and whatever the notebook returned.
- `run_project(action="collect", day=..., arm=..., scan_id=...)` buys one
  archive rescan. It runs the current crawler rule set over the raw ingest the
  archive still holds for that day and arm, returns the count, appends the
  receipt to `audit_receipts.json` and spends a unit. Sending the same
  `scan_id` again returns the same receipt without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the archive service, and
  nothing it writes is kept.
