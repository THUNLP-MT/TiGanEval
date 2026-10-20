# Plate screen review

This is the thermal bench's workspace for the July heat-spreader screen. What
the design review has asked the bench for is in `design_review_note.md`.

## What is here

- `screen_context.json` is the screen as the reporting job publishes it: the
  campaign, the twelve plates and which one the review is about, the stored
  incumbent number and the day it was read, the screen table run by run, the
  rig log, the booking terms and the review's own note.
- `screen_ledger.csv` is the same screen table as a spreadsheet, one row per
  run.
- `bench_notes.md` is how the rig and the reporting job work, as the bench
  wrote it down.
- `rig_log.md` is the log the operator keeps for every day the rig ran.
- `booking.md` is the rig sheet: what is left, what a day holds, what is on the
  shelf.
- `baseline_characterisation.md` is the incumbent module's own measurement.
- `design_review_note.md` is what the review asked for and by when.
- `project_records/` holds the four working days this review has had, each with
  the operator's notes and the evidence as it stood that day.
- `bench_receipts.json` is the rig's receipt stream. The rig writes it; the
  notebook cannot. It is the only record of what the review has been charged
  for.
- `protocol.py` is the shape the reporting tooling calls the notebook through
  and reads its answer in. It ships with the tooling, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the review as it
  currently runs: the plate's screen score as the number, a spread from the runs
  behind it, and a sheet that puts the days that are left on the plate.
  `support.py` is empty.

## What the notebook has to do

`analyze(context, receipts)` returns the report, and
`next_collection(context, receipts)` returns the sheet for the next rig day or
`"stop"`. `protocol.py` documents both. The same file runs the screens queued
behind this one.

## Tools

- `run_project(action="status")` prints the current rig-day budget, a summary
  of each charged booking, the working days on record and a source-file directory.
  The source files hold the booking terms, review note and full measurements.
- `run_project(action="replay", record="project_records/<name>.json")` opens one
  working day: the operator's notes, the evidence cutoff and receipt ids,
  references to the source files, and whatever the notebook returns for it.
  When the receipt stream has moved on since that day it also prints the current
  booking totals, receipt ids and the notebook's current answers.
- Add `include_inputs=true` to that replay call for the complete `context` and
  `receipts` used for each answer, with the historical and current inputs labelled
  separately. Source files describe the current workspace; a historical replay
  uses the earlier snapshot. You can read the source files directly or use these
  exact inputs in `run_experiment`.
- `run_project(action="collect", day=[{"part": ..., "runs": ...}, ...],
  booking_id=...)` books the next rig day. The rig runs the sheet, writes a
  receipt into `bench_receipts.json` and takes the day off the booking sheet. A
  sheet the desk will not take comes back with a reason and the day is charged
  all the same. Sending the same `booking_id` again returns the day it already
  ran without charging anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the rig, and nothing it
  writes is kept.
