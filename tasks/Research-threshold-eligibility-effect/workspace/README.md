# Northgate standing-score offer campaign

Growth operations. Everything the campaign readout runs on is in here, together
with the council minute, the desk's grant and the notes from each working
session the campaign has had.

## What is here

- `campaign_context.json` is the campaign as the reporting job publishes it: the
  window, the line, the credit ceiling, the order window, the day the export
  stops and how late an order reaches it, the review grant and the council's own
  note.
- `project_records/offer_register.csv` is one row per account: the run week and
  whether the run scored it or carried it, the standing score the register
  carries today, the credit filed against it, whether the offer went out and
  when, the first order the export carries after that offer, and the last day
  the export watched the account. `scoring_run_notes.md` describes the run and
  the columns.
- `project_records/recompute_log.csv` is one row per account each refresh batch
  touched: the batch, the day it landed and the score the account carried before
  it.
- `export_note.md` is data platform's note on where the export stops.
- `council_minute.md` is what the council asked for and the terms it set.
- `review_grant.md` is the account review desk's grant and what it will and will
  not pull.
- `review_receipts.json` is the desk's own receipt stream, written by the desk
  and not by the notebook. What this campaign has been charged for is in there
  and nowhere else, together with the files each lot returned.
- `project_records/` also holds the four working sessions this campaign has had,
  each with the analyst's notes and the evidence as it stood that day.
- `protocol.py` travels with the growth reporting stack: it is how the stack
  calls a notebook and how it reads the answer back, so it is not ours to
  change.
- The two files this team owns are `analysis.py` and `support.py`. `analysis.py`
  is the readout as it runs today: order rate above the line against order rate
  below it on the whole register, the usual range around the difference, and a
  next lot of files pulled from the accounts that took the offer. `support.py`
  has nothing in it yet.

## What the stack expects back

`analyze(context, receipts)` returns the readout and
`next_review(context, receipts)` returns the next lot of files to ask the desk
for, or `"stop"`. `protocol.py` documents both, and the register and the
recompute log reach the notebook as `context["register"]` and
`context["recompute"]`. The copies under `project_records/` are this campaign's
own; the same notebook runs the other markets on the council's slide.

## Tools

- `run_project(action="status")` prints the campaign, the council's terms, how
  many review files are charged and left, every lot on the receipts and the
  working sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's analyst ran it — the evidence as it stood on
  the day, the lots on file by then — and prints the session's notes, the rows
  by standing score around the line and by run week, and whatever the notebook
  handed back.
- `run_project(action="collect", week=..., band=..., above_share=...,
  files=..., receipt_id=...)` asks the review desk for a lot. It returns the
  files with the score the run used, the credit filed against each account and
  its ordering to today, appends the receipt to `review_receipts.json` and
  charges the grant. The desk refuses some lots and charges for them anyway.
  Sending the same `receipt_id` again returns the same receipt without charging.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the review desk, and
  nothing it writes is kept.
