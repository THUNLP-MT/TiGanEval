# Halstow dispatch board

This is the dispatch desk's reporting workspace. One board a month goes to the
contact centre and the regional service manager, off this notebook, about the
arrival window the depot prints on every crew card.

## What is here

- `dispatch_traffic.csv` is the monthly traffic report: how many jobs of each
  class the depot dispatched.
- `audit_intake_log.csv` is the audit desk's weekly record of the sheet pull:
  what was asked for, what was pulled, how many came back with a duration, and
  the close-out form version they were written on.
- `audit_sheets.csv` is the sheets themselves, one row a job, with the five
  facts the tool reads, the tool's number and the close-out duration.
- `field_ops_note.md` is how a job reaches the board and how the sheets reach
  the desk, as the dispatch floor wrote it down, with the releases and the
  night roster.
- `board_commitment.md` is what the window promises and what the contact
  centre's miss log recorded in June.
- `audit_desk.md` is what the month's audit nights pay for and what the desk
  turns away.
- `project_records/` holds the four working records this month has had, each
  with its author's notes, the evidence as it stood that week and the visits
  that had been billed by then.
- `visit_receipts.json` is the audit desk's sealed receipt file. The desk
  writes it; the notebook cannot. Each receipt carries the jobs the crew timed.
- `board/` is the duration tool as it runs when a job is booked, with the model
  the planning team fitted.
- `protocol.py` is the shape the dispatch stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the board as it
  currently runs: one cut over the whole sheet file, that window printed for
  every class, and four nights booked on the busiest class. `support.py` is
  empty.

## What the notebook has to do

`analyze(context, receipts)` returns the board, and
`next_collection(context, receipts)` returns the next night to book or
`"stop"`. `protocol.py` documents both. The same file runs the other depots in
the region.

## Tools

- `run_project(action="status")` prints the depot, the month, the board's
  terms, the audit terms and roster, the traffic report, how many units are
  spent and left, every visit on the receipts and the records on file.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that record's author ran it: on the evidence as it stood
  that week and the visits billed by then, and prints the record's notes and
  intake log beside whatever the notebook returned.
- `run_project(action="collect", week=..., job_class=..., jobs=...,
  receipt_id=...)` books one night visit. The crew times the jobs and hands the
  durations back, the receipt is appended to `visit_receipts.json` and the
  units are spent. A request the desk turns away still costs a unit. Sending
  the same `receipt_id` again returns the same receipt without spending
  anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the audit desk, and
  nothing it writes is kept.
