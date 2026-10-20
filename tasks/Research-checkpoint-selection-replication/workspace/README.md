# August ranking release readout

This is the ranking team's release workspace. One readout a campaign goes to
the platform release board, off this notebook, about the checkpoint the team is
asking to promote.

## What is here

- `run_ledger.csv` is the training pipeline's export: one row for every
  automatic evaluation it ran, with the run, its `init_id`, its warm-up, the
  checkpoint step, the `val_score` it came back with, the lot and row count it
  was scored on, the run's compute cost and the trainer version.
- `curves/<run_id>.csv` is what each run's own training job wrote as it went:
  step, tokens seen, training loss and the loss on the run's held-back split.
- `checkpoint_registry.csv` is what is on disk. The retention job clears
  checkpoints when the quota runs out; a checkpoint that is gone cannot be
  scored again.
- `lot_note.md` is the platform rota's log of the validation lots.
- `release_note.md` is the model in production, the figure the release note
  stores for it and the promotion rule of record.
- `compute_ledger.md` is the campaign's grant, what has gone, what is left and
  the desk's rate card.
- `review_request.md` is what the board asked for and when.
- `project_records/` holds the four working records this campaign has had, each
  with its author's notes, which runs had finished by then and which desk jobs
  had been billed.
- `ledger/receipts.jsonl` is the evaluation desk's sealed receipt stream. The
  desk writes it; the notebook cannot. It is the only record of what the
  campaign was billed for, and each receipt carries the reads it returned.
- `protocol.py` is the shape the release tooling calls the notebook through and
  reads its answer in. It ships with the tooling, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the readout as it
  currently runs: the best row of the run ledger against the stored release
  figure, the top five rows' spread either side of it, and a plan that queues
  two more training runs of the configuration behind that row. `support.py` is
  empty.

## What the notebook has to do

`analyze(context, ledger)` returns the readout and
`next_collection(context, ledger)` returns the next desk job or `"stop"`.
`protocol.py` documents both. The same file runs the campaigns that follow this
one.

## Tools

- `run_project(action="status")` prints the campaign, the release it is measured
  against, the lots the desk can score on, the compute terms, every job on the
  receipt stream and the records on file.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that record's author ran it: on the evidence as it stood that
  day and the desk jobs that had been billed by then, and prints the record's
  notes beside whatever the notebook returned.
- `run_project(action="collect", job_id=..., kind="reads", lot=..., items=[...],
  repeats=...)` sends one job to the evaluation desk. It returns the reads,
  appends the receipt to `ledger/receipts.jsonl` and spends the units.
  `kind="train"` queues training runs instead. A job the desk will not run comes
  back with the queue fee charged. Sending the same `job_id` again returns the
  same receipt without spending anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the evaluation desk, and
  nothing it writes is kept.
