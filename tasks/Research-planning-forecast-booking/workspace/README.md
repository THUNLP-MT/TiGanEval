# Dispatch desk, week 38

This is the desk's workspace for the week 38 campaign. What the weekly pack has
to carry is in `review_note.md`.

## What is here

- `harbour_shift_forecast.csv` and `ridge_shift_forecast.csv` are the two areas'
  planning engines' own exports, one row per stamp, window and zone.
- `network_area_forecast.csv` is the network's own line: one total per area and
  shift, no window split.
- `routing_table.csv` is the zone-to-area map with its effective dates.
- `zone_coverage.md` is Harbour's own coverage sheet.
- `carrier_agreement.md` is what the desk books under: the van rate, what a
  short window costs, the caps, the minimum order, the reservation window, the
  desk fee and the quarter's allowance.
- `desk_log.md` is Tomás's log: how the sheets and the meter arrive, and a line
  for every shift this campaign has settled.
- `review_note.md` is what the depot managers and finance take out of the pack.
- `project_records/` holds the four working days this campaign has had, each
  with the planner's notes and the evidence as it stood that day.
- `ledger/receipts.jsonl` is the settlement ledger. The meter writes it; the
  notebook cannot. It is the only record of what the desk has been charged for.
- `desk_context.json` is the whole publication in one object, in the shape the
  notebook is called with. The two CSVs are the same rows, easier to read.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answers in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the sheet as it
  currently runs: the newest rows off both engines, a range off how far the
  meter has come off the sheet, and an order at eighteen drops a van.
  `support.py` is empty.

## What the notebook has to do

`analyze(context, receipts)` returns the pack's sheet, and
`next_collection(context, receipts)` returns the order for the next shift or
`"stop"`. `protocol.py` documents both. The same file runs the campaigns queued
behind this one.

## Tools

- `run_project(action="status")` prints the shift calendar, the carrier terms,
  the allowance left, every order the desk has been charged for and the working
  days on record.
- `run_project(action="replay", record="project_records/<name>.json")` opens one
  working day: the sheets and the ledger as they stood then, the planner's
  notes, and whatever the notebook returns for it. When the ledger has moved on
  since that day it prints the desk as it stands now beside it.
- `run_project(action="collect", shift=..., order=[{"area": ..., "window": ...,
  "vans": ...}, ...], order_id=...)` puts an order on the road. The carrier runs
  the shift, the meter writes a receipt into `ledger/receipts.jsonl` and the
  van-hours come off the allowance. An order the carrier will not take comes
  back with a reason and the desk fee is charged all the same. Sending the same
  `order_id` again returns the order it already ran without charging anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the carrier, and nothing
  it writes is kept.
