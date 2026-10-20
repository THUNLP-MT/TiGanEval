# One-tap reorder watch

Growth analytics, mobile. Everything the weekly readout runs on is in here,
together with the charter the board and finance signed and the notes from each
working session the watch has had.

## What is here

- `watch_context.json` is the watch as the weekly job publishes it: the window,
  the line the watch is judged against, the fourteen-day reorder window, the
  share cap and its review day, the topics, the looks taken, the share-day
  grant, the audience roll-up, the enrolment snapshot, the reorder publications
  and the ingestion receipts.
- `enrolment_snapshot.csv` is one row per day, arm and `sessions_28d` count,
  with the users who entered the watch that day. `sessions_28d` is the number of
  sessions that user had in the 28 days before they entered.
- `reorder_publications.csv` is one row per enrolment day, arm, `sessions_28d`
  count and publication day, with the reorders in the table for it.
- `ingestion_receipts.json` is what the collector wrote for the reorder topic:
  `accepted`, `dropped` and the topic's `ceiling_events`, day by day.
- `base_audience.json` is the monthly audience roll-up: how many people the app
  has at each `sessions_28d` count.
- `rollout_charter.md` is the terms the growth board, finance and platform
  agreed before the watch opened, with the minute finance keeps on the file.
- `reliability_review.md` is platform's review of the ingest incident.
- `look_notes.md` is what the weekly readout has said at each look.
- `project_records/` holds the four working sessions this watch has had, each
  with the analyst's notes and the evidence as it stood that day.
- `collection_ledger.json` is the booking receipt stream, written by the traffic
  service and not by the notebook. What this watch has been billed for is in
  there and nowhere else.
- `protocol.py` travels with the growth reporting stack: it is how the stack
  calls a notebook and how it reads the answer back, so it is not ours to
  change.
- The two files this team owns are `analysis.py` and `support.py`. `analysis.py`
  is the readout as it runs today: arm totals over the users the job has
  finished measuring, the usual interval, the call against the line, and a plan
  that asks for as much traffic as it can get for a week. `support.py` has
  nothing in it yet.

## What the stack expects back

`analyze(context, ledger)` returns the readout, and
`next_collection(context, ledger)` returns the next booking to make or
`"stop"`. `protocol.py` documents both. The same file runs the other watches on
this stack.

## Tools

- `run_project(action="status")` prints the watch, the charter's terms, how many
  share-day points are spent and left, every booking on the ledger and the
  working sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's analyst ran it — the evidence as it stood on
  the day, the bookings paid for by then — and prints the session's notes, that
  day's numbers and whatever the notebook handed back.
- `run_project(action="collect", share_pct=..., days=..., hold_ramp=...,
  call_id=...)` books the watch forward. It serves that treated share of new
  enrolments for that many days, returns those days' enrolment rows, the
  reorders the table gained on each of them by arm, and the topic's counters,
  appends the receipt to `collection_ledger.json` and spends the share-day
  points. Sending the same `call_id` again returns the same receipt without
  spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the traffic service, and
  nothing it writes is kept.
