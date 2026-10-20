# QR-40 burst qualification

Reliability, coupling line. Everything the submission report runs on is in
here, together with the plan the submission was signed off against and the
notes from each working day the qualification has had.

## What is here

- `stress_context.json` is the lot as the reporting job publishes it: the lot,
  the family, the build month, the hold the plan is written against, the
  fraction the submission is about, the console's sticker span, the dead-weight
  block's own pressure, the cartridges on the shelf, the benches and when one is
  out of service, the chamber budget, what the stores hold, the days the
  scheduler is holding, the bench sheet and the whole run table.
- `burst_runs.csv` is one row per coupling the qualification put on a bench:
  `unit_id`, `batch`, `bench`, `cartridge`, `reading_bar`, `dwell_min`,
  `result`. `reading_bar` is what that bench's console wrote. `result` is
  `leak` or `hold`, and `block` on the dead-weight block's own rows.
- `bench_sheet.md` is what the bench wrote for each batch: which bench, which
  cartridges, what hold, the sticker on the console and the two dead-weight
  block readings at the batch's ends.
- `booking.md` is the chamber budget and the desk's terms: hours left, ports,
  what an hour is charged for, when a bench is out, what the stores hold.
- `qualification_plan.md` is what the submission needs, and the lots queued
  behind this one.
- `project_records/` holds the four working days this qualification has had,
  each with the operator's notes and the evidence as it stood that day.
- `session_receipts.json` is the chamber receipt stream, written by the desk
  and not by the notebook. What this review has been charged for is in there
  and nowhere else.
- `protocol.py` travels with the reliability reporting tooling: it is how the
  tooling calls a notebook and how it reads the answer back, so it is not ours
  to change.
- The two files this team owns are `analysis.py` and `support.py`.
  `analysis.py` is the report as it runs today: a leak fraction per cartridge
  against what the console wrote, a straight line through them, the pressure
  where that line reaches one in ten, a range off the scatter, and a next
  session on the top cartridge. `support.py` has nothing in it yet.

## What the tooling expects back

`analyze(context, receipts)` returns the report, and
`next_block(context, receipts)` returns the next session to put in front of the
desk or `"stop"`. `protocol.py` documents both. The same file runs the lots
queued behind this one.

## Tools

- `run_project(action="status")` prints the lot, the plan's terms, how many
  chamber hours are spent and left, what the stores hold, every session on the
  receipts and the working days on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that day's operator ran it — the evidence as it stood then,
  the sessions charged by then — and prints the day's notes, that day's bench
  sheet and ladder, and whatever the notebook handed back.
- `run_project(action="collect", bench=..., batch=..., cartridge=...,
  dwell_min=..., units=..., booking_id=...)` puts one sheet in front of the
  chamber desk. It returns that session's per-unit readings and results and the
  bench's block readings for it, appends the receipt to
  `session_receipts.json` and charges the hour. Sending the same `booking_id`
  again returns the same receipt without charging anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the chamber desk, and
  nothing it writes is kept.
