# Scaling sweep readout

This is the modelling group's workspace for the `athena-summer` sweep. The
group asks one thing of it: what loss this architecture reaches at ten times
the compute of the sweep's biggest job, and what the compute that is left
should buy.

## What is here

- `sweep_context.json` is the sweep as the queue publishes it: the queue's
  terms, the block table, the shard table, one summary row per job, the loss
  curve each job wrote, and the change log.
- `sweep_receipts.json` is the queue's receipt stream for this quarter's grant.
  The queue writes it; the notebook cannot. It is the only record of what the
  grant has paid for.
- `data_manifest.md` is what the training mixture is built from, what each
  validation shard was cut from, and how the loader resolves a shard index.
- `compute_ledger.md` is the grant, the charging rule, the queue's limits, what
  the compute committee books a quarter against, and what the sweeps on this
  queue have spent.
- `queue_notes.md` is how a job runs: reservations, training, validation, and
  the tuning sheet the group works from.
- `project_records/` holds the four working sessions this sweep has had, each
  with the operator's notes and the summary table as it stood that day.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` came off the spring
  sweep and holds the readout as it currently runs: a line through loss against
  log compute over the whole table, the value at ten times the biggest job, the
  spread of the points around the line, and the width-512 run as the next
  booking. `support.py` is empty.

## What the notebook has to do

`analyze(context, receipts)` returns the readout and `next_run(context,
receipts)` returns the job to book next or `"stop"`. `protocol.py` documents
both. The same file runs the other sweeps on this queue.

## Tools

- `run_project(action="status")` prints the sweep, the queue's terms, the units
  spent and left, the shard and block tables, every job on the receipt stream
  and the sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's operator ran it: on the summary table as it
  stood that day, printing the session's notes and rows beside whatever the
  notebook returned.
- `run_project(action="collect", width=..., data=..., learning_rate=...,
  val_shard=..., job_id=...)` books one training job. It returns the final loss
  and the curve, appends the receipt to `sweep_receipts.json` and charges the
  grant. Sending the same `job_id` again returns the same receipt without
  charging.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the queue, and nothing it
  writes is kept.
