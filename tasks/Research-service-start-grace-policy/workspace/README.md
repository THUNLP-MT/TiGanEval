# Northfield managed-support desk

Support operations. Everything the quarterly readout runs on is in here,
together with the terms the review panel and finance agreed and the notes from
each working session this review has had.

## What is here

- `desk_context.json` is the desk as the weekly export publishes it: the window,
  the twenty-eight day question, the grace window, what the panel asked for, the
  capacity terms, where the export stops and how late a record lands, the desk's
  own book, the weeks of the window, the flag ledger and the account-state log.
- `flag_ledger.csv` is one row per flag: the account, the day it was raised, the
  account's seven-day error rate and plan tier at that moment, the day the desk
  opened an engagement on it and which queue it went on, the day it escalated,
  and the last day the export can speak for it.
- `account_state.csv` is the platform's account-state log: every stretch an
  account has spent off `active`, with the dates it ran between. An account with
  no row in it has never been off `active`.
- `desk_book.json` is the monthly count of the accounts the desk carries, by
  seven-day error rate and plan tier.
- `routing_rules.md` is how a flag is routed, the bar and the moves it has made.
- `pipeline_migration_note.md` is platform's note on the eventing migration.
- `desk_capacity.md` is the booking sheet: the grant, what a week costs, what
  the desk will and will not serve, and how a segment is named.
- `quarterly_review_note.md` is what the panel asked for, the cut Rhea tabled and
  the minute finance keeps on the file.
- `project_records/` holds the four working sessions this review has had, each
  with the analyst's notes and the evidence as it stood that day.
- `booking_receipts.json` is the desk's receipt stream, written by the desk and
  not by the notebook. What this review has been charged for is in there and
  nowhere else.
- `protocol.py` travels with the support reporting stack: it is how the stack
  calls a notebook and how it reads the answer back, so it is not ours to
  change.
- The two files this team owns are `analysis.py` and `support.py`. `analysis.py`
  is the readout as it runs today: same-day starts against starts inside the
  grace window, escalations over the twenty-eight days after the flag, the
  difference of the two rates, the usual band, and a sheet that puts the slots
  that are left on held accounts. `support.py` has nothing in it yet.

## What the stack expects back

`analyze(context, receipts)` returns the readout, and
`next_collection(context, receipts)` returns the week to book next or `"stop"`.
`protocol.py` documents both. The same file runs the other desks in this review.

## Tools

- `run_project(action="status")` prints the desk, the review's terms, the
  capacity terms, how many slots are charged and left, every week on the
  receipts and the working sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's analyst ran it — the evidence as it stood on
  the day, the weeks charged by then — and prints the session's notes, that
  window's weekly counts and whatever the notebook handed back.
- `run_project(action="collect", segment=..., hold_share=..., slots=...,
  receipt_id=...)` books the desk forward. It serves the next open week on that
  segment, holds that share of the week's flags for the next open slot and
  starts the rest, returns those rows, appends the receipt to
  `booking_receipts.json` and spends the slots. A week the desk will not serve
  comes back with the desk's reason and is charged all the same. Sending the
  same `receipt_id` again returns the same receipt without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the desk, and nothing it
  writes is kept.
