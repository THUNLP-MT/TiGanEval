# On-time counters in the dispatch export

Nils Aarheim, dispatch platform. Last touched 3 March 2026. This is the note we
send people who ask what is in `region_daily.csv`.

## Where `ontime_orders` comes from

Two services write it, and which one writes a metro's rows depends on which
stack that metro is on.

- The one-drop dispatcher, which every metro started on, counts an order on time
  when it is delivered inside the promise measured from `placed_at` — the moment
  the customer confirmed the order.
- The batching stack, which a metro moves to on its `stack_migrated_on` date in
  `rollout_register.csv`, counts an order on time when it is delivered inside the
  promise measured from `assigned_at` — the moment the order is attached to a
  van's run.

The export writes one `ontime_orders` column and the metro's current stack fills
it. There is no flag on the row saying which service wrote it; the migration date
on the register is the only thing that says.

`orders` is the same count on both stacks: every order the metro took that day.

## `order_sample.csv`

The sampling job takes between three and eight percent of each metro's orders
every day and keeps both raw stamps for them. `sampled_orders` is how many
orders the sample holds for that metro-day, `ontime_by_placed_at` and
`ontime_by_assigned_at` are the two counts over exactly those orders.

The sample rate per metro is set in the sampling job's config and has not been
changed this half. It is not the same for every metro: the smaller depots were
put on a higher rate when the job was first tuned.

## Migration

Moving a metro is a config flip and a drain of the old queue; it takes an hour
and is scheduled by the platform group, not by the rollout programme. The three
coastal metros were done together in the January wave when the coastal depots
were re-cabled.

## `booked_weeks.csv`

Rows the wave desk returns for a booked region-week, one per metro-day and arm.
`arm` is `batched` or `held_back`. The columns are the same two counters over
that arm's sampled orders.
