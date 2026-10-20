# How a job runs on this queue

Queue engineering keeps this page. It covers what happens to a reservation
between the submission form and the summary row it leaves behind, and it holds
for every sweep on the shared queue.

## Reservations

A reservation names a width, a number of training examples, a learning rate and
a validation shard index. Jobs run on whichever machines come free, so the
order of the summary table is the order the queue had room, not an order anyone
chose.

The scheduler prints the charge at submission and refuses a reservation outside
the accepted range. A refused reservation leaves nothing behind on the table.

## Training

Every job runs one pass over its examples at batch size 8, so the `steps`
column is the example count divided by eight. Nothing in a job is resumed from
another job; each starts from a fresh initialisation.

## Validation

A job writes a validation loss at each of forty evenly spaced checkpoints, and
the last of those is the `final_val_loss` column on the summary table. The full
curve is kept beside the row under `curves` in `sweep_context.json`, as
`[step, loss]` pairs.

Validation always runs on one shard, named by `val_shard_id`, and the shard the
job gets comes from the loader. `data_manifest.md` says which block each shard
was cut from and which loader resolves an index against which list.

## Tuning sheet

The tuning sheet the group works from suggests a learning rate by width band:
roughly 0.026 to 0.032 under width 96, 0.022 to 0.028 from 96 to 176, and 0.016
to 0.024 from 192 up. The sheet is a suggestion; the queue takes whatever rate
the submission form is given, and the `learning_rate` column is what a job
actually ran at.

For comparison reservations, allocation calls a shape new only at or under two
thirds of the table's lowest examples-per-width ratio, or at or over one and a
half times its highest.
