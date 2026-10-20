# EM-9 soak qualification

Reliability, emitter line. Everything the March soak report runs on is in here,
together with the plan the review was opened against and the notes from each
working day the campaign has had.

## What is here

- `soak_context.json` is the campaign as the reporting job publishes it: the
  campaign and family, the build month, the drive and case temperature the
  specification is written against, the share of output the figure is about,
  the bench meter's full scale and its repeat spread, the reference source and
  the id its rows carry, the racks, the decay catalogue, the module index, the
  whole trace export, the chamber budget and its caps, what the shop holds in
  spares, when the rig is out for service and the days the schedule is holding.
- `project_records/soak_traces.csv` is the trace export, one row per bench
  reading: `module_id`, `lot`, `rack`, `drive_a`, `sample_index`, `logged_at`,
  `elapsed_h`, `output_mw`. `sample_index` and `elapsed_h` come off the rack
  logger's own sample counter; `logged_at` is the rack clock's stamp on the
  reading session; `output_mw` is what the bench meter wrote. The reference
  source's own reads are in the export under the id `soak_context.json` gives
  for it.
- `module_index.csv` is goods-in: each module's lot, rack, drive, the output
  the reference meter read it at on the way in, and the day it went on soak.
- `bench_sheet.md` is the meter: the sticker on its front, its repeat spread,
  and the reference source read into the export at every session.
- `rack_log.md` is the rack diary: what was loaded when, and what maintenance
  each logger has had.
- `decay_catalogue.md` is the reliability catalogue for this family: the four
  decay laws it carries, the shape each one puts on soak, the drive form it was
  calibrated with and what ten degrees of case temperature do to it.
- `chamber_plan.md` is what the review needs and what the chamber desk's terms
  are: days left, ports, what a block is charged, the caps, the spares, the
  service window and the date the review sits.
- `soak_receipts.json` is the chamber receipt stream, written by the desk and
  not by the notebook. What this review has been charged for is in there and
  nowhere else.
- `protocol.py` travels with the reliability reporting tooling: it is how the
  tooling calls a notebook and how it reads the answer back, so it is not ours
  to change.
- The two files this team owns are `analysis.py` and `support.py`.
  `analysis.py` is the report as it runs today: loss for every bench row
  against the row its module opened at, pooled on `elapsed_h`, a straight line
  through log loss against log hours, the hours where that line reaches a
  tenth, a range off the scatter, and a next block at 1.7 A. `support.py` has
  nothing in it yet.

## What the tooling expects back

`analyze(context, receipts)` returns the report, and
`next_block(context, receipts)` returns the next block to put in front of the
desk or `"stop"`. `protocol.py` documents both. The same file runs the
campaigns queued behind this one.

## Tools

- `run_project(action="status")` prints the campaign, the plan's terms and
  caps, the catalogue, how many chamber days are spent and left, what the shop
  holds in spares, every block on the receipts and the working days on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that day's operator ran it — the export as it stood then,
  the blocks charged by then — and prints the day's notes, the module index,
  the export module by module, and whatever the notebook handed back.
- `run_project(action="collect", drive_a=..., case_temp_c=..., ports=...,
  chamber_days=..., lot=..., block_id=...)` puts one block in front of the
  chamber desk. It returns that block's spare modules with their incoming
  readings and every bench row it came back with, appends the receipt to
  `soak_receipts.json` and charges the days. Sending the same `block_id` again
  returns the same receipt without charging anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the chamber desk, and
  nothing it writes is kept.
