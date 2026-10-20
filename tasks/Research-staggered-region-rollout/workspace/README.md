# Halcombe batching rollout

Rollout programme, Halcombe network. Everything the board readout runs on is in
here, together with the wave board's standing minute and the notes from each
working session the programme has had.

## What is here

- `rollout_context.json` is the network as the reporting pipeline publishes it:
  the window, the bar the board acts inside, how many days of a metro the board
  reads and how many before it, the wave capacity terms, the region book, the
  rollout register, the daily export, the order sample, the dispatch on-call log
  and any booked weeks the wave desk has served.
- `rollout_register.csv` is one row per metro: its service band, its
  `readiness_score`, the day batching went live on it (empty if it has not), the
  day its dispatch stack migrated, and the orders a day it was running when the
  register was last refreshed.
- `region_daily.csv` is one row per metro-day: orders taken, `ontime_orders` as
  the dispatch export counts them, and the rate of the two.
- `order_sample.csv` is one row per metro-day for the sampled orders: how many
  were sampled and the on-time count on each of the two raw stamps.
- `region_book.json` is the region book cut on 1 February, with the orders each
  of its metros was running that day, and the day the board's window closes.
- `dispatch_incident_log.md` and `dispatch_incident_log.json` are the dispatch
  on-call log for the window, one line per page or change.
- `pipeline_schema_note.md` is the platform group's note on what is in the
  export and in the sample.
- `wave_board_minute.md` is the wave board's standing minute: the book, the bar,
  the grant and the terms the wave desk serves on.
- `booked_weeks.csv` holds the rows a booked region-week returns, one per
  metro-day and arm. It is empty until the programme books one.
- `project_records/` holds the four working sessions this programme has had,
  each with the analyst's notes and the evidence as it stood that day.
- `wave_receipts.json` is the receipt stream, written by the wave board and not
  by the notebook. What this programme has been charged for is in there and
  nowhere else.
- `protocol.py` travels with the programme reporting stack: it is how the stack
  calls a notebook and how it reads the answer back, so it is not ours to
  change.
- The two files this programme owns are `analysis.py` and `support.py`.
  `analysis.py` is the readout as it runs today: a metro term and a week term
  fitted to the printed on-time rate, the coefficient on being live, the usual
  range around it, and a plan that puts the wave capacity on the biggest metros
  already running batching. `support.py` has nothing in it yet.

## What the stack expects back

`analyze(context, receipts)` returns the readout and
`next_collection(context, receipts)` returns the region-week to book next or
`"stop"`. `protocol.py` documents both. The same file produces the readout for
the other networks on this stack.

## Tools

- `run_project(action="status")` prints the rollout, the board's terms, the
  region-weeks charged and left, every receipt on the ledger and the working
  sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's analyst ran it — the evidence as it stood on
  the day, the receipts charged by then — and prints the session's notes, the
  metros it walked day by day, and whatever the notebook handed back.
- `run_project(action="collect", region=..., week=..., holdback_share=...)`
  books one metro for one week with that share of its orders held back from
  batching. It returns the week's rows for both arms, appends the receipt to
  `wave_receipts.json` and charges the region-week. The board hands a week back
  rather than serving it when its own terms do not allow it, and charges for
  that too. Asking again for a region-week already on the receipts returns that
  receipt without charging.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the wave desk, and nothing
  it writes is kept.
