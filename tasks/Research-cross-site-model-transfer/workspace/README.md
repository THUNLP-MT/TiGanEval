# Brookfield triage report

This is the triage service's reporting workspace. One report a quarter goes to
each centre's manager, off this notebook, about the pipeline that scores their
tickets at intake.

## What is here

- `brookfield-intake-counters.csv` is the intake system's daily counter export
  for this quarter: received, queued, passed over without a history panel, and
  the rows the weekly reconciliation export carried.
- `brookfield-ops-note.md` is how tickets reach a reviewer here, as the floor
  leads wrote it down.
- `label-budget.md` is what the quarter pays for and what the two centre
  managers asked for, with the April staffing paper the range clause came out
  of.
- `project_records/` holds the four working records this quarter has had, each
  with its author's notes, the evidence as it stood that day and the reviews
  that had been paid for by then.
- `label_ledger.json` is the review desk's sealed ledger. The desk writes it;
  the notebook cannot. It is the only record of what the quarter was billed
  for, and each receipt carries the reviewed rows it returned.
- `ridgeline_reserved_split.csv` is the reserved Ridgeline split: the rows the March
  fit did not train on, with the pipeline's decision and the reviewer's verdict
  on each.
- `pipeline/` is the scorer as it runs at intake, with the column statistics
  and the weights the March build shipped.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the report as it
  currently runs: the reserved Ridgeline split's error, the usual interval
  around it, and a plan that buys more Ridgeline queue reviews. `support.py` is
  empty.

## What the notebook has to do

`analyze(context, ledger)` returns the report, and
`next_collection(context, ledger)` returns the next review request or `"stop"`.
`protocol.py` documents both. The same file runs the other centres the pipeline
is shipped into.

## Tools

- `run_project(action="status")` prints the deployment, the intake settings,
  the review terms, the shipped model's manifest, how many units are spent and
  left, every review on the ledger and the records on file.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that record's author ran it: on the evidence as it stood
  that day and the reviews that had been paid for by then, and prints the
  record's notes and counters beside whatever the notebook returned.
- `run_project(action="collect", site=..., channel=..., rows=...,
  receipt_id=..., prior_contacts_min=..., prior_contacts_max=...)` puts one
  review request through a channel. It returns the reviewed rows, appends the
  receipt to `label_ledger.json` and spends the units. Sending the same
  `receipt_id` again returns the same receipt without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the review desk, and
  nothing it writes is kept.
