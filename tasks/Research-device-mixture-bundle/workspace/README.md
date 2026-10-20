# Harrowgate bundle board pack

This is the handheld train's release workspace. One board pack a quarter goes
to the handheld board, off this notebook, about the label-reading bundle every
depot on the train would run.

## What is here

- `capture_log.csv` is the capture exporter's own export for this window: one
  row a capture, with the device it came off, the firmware that device was on,
  the capture condition, the eight columns the sensor writes, the annotator's
  reading, each bundle's decision on the row as the exporter wrote it, and the
  `stage` the exporter stamped on it.
- `fleet_register.csv` is what the depot keeps: every unit in service, the bay
  it works in, the firmware it runs, the mixture of conditions it captures in,
  and the day it went into service.
- `firmware_4_2_release.md` is platform's release note for the 4.2 firmware.
- `bundle_cards.md` is what came with the bundle drop, plus what our release
  engineering wrote down about each pool.
- `annotation_budget.md` is what the quarter pays for, what a request may ask
  for and what the desk charges, including the two requests it handed back.
- `board_minute.md` is the minute of the meeting that deferred the decision.
- `project_records/` holds the four working records this campaign has had, each
  with its author's notes, the export and requests that had been billed by
  then. Replay reads that dated evidence through the current fleet register
  for this board.
- `capture_receipts.json` is the annotation desk's sealed receipt file. The
  desk writes it; the notebook cannot. It is the only record of what the
  campaign was billed for, and each receipt carries the rows it returned.
- `bundles/` is the vendor's scorer as it runs on a unit, with `cards.json`
  holding each bundle's front end and weights.
- `protocol.py` is the shape the release stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the pack as it
  currently runs: each bundle's accuracy across the export, the interval around
  the best one, and a plan that buys more counter captures. `support.py` is
  empty.

## What the notebook has to do

`analyze(context, receipts)` returns the board pack, and
`next_collection(context, receipts)` returns the next capture request or
`"stop"`. `protocol.py` documents both. The same file runs the fleets behind
this one.

## Tools

- `run_project(action="status")` prints the campaign, the firmware settings,
  the annotation terms, how many credits are spent and left, every request on
  file and the records on file.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that record's author ran it: on the evidence as it stood
  that day and the requests that had been billed by then, and prints the
  record's notes and counts beside whatever the notebook returned.
- `run_project(action="collect", duty_profile=..., firmware=..., condition=...,
  rows=..., receipt_id=...)` puts one capture request to the annotation desk.
  It returns the annotated rows, appends the receipt to
  `capture_receipts.json` and spends the credits. Sending the same
  `receipt_id` again returns the same receipt without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the annotation desk, and
  nothing it writes is kept.
