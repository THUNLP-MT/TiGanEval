# Compute grant, reservation capacity 2027 Q1

The modelling group's quarters are queued on one shared grant. The console bills
in sampler steps and writes a receipt for every job, served or refused.

## The terms

- **Granted this quarter:** 24,300 steps.
- **Spent at the last accounting:** 6,710 steps. That covers the exploratory
  fits run in December, before the console started keeping receipts on this
  quarter. Those runs were not kept and are not in `chains/`.
- **Cap on one job:** 4,000 steps. The scheduler will not queue a single job
  larger than that while the cluster is shared with the forecasting group.
- **Smallest job:** 600 steps. Anything under that spends more on scheduling
  than it returns and the console sends it back.
- **A refused job:** 250 steps. The console charges the queue slot whether or
  not it ran anything.

## What is left

Everything the console has billed this quarter is on `collection_receipts.json`,
one entry per job, with the steps it asked for, the steps it returned, the steps
it charged and the refusal line if it was sent back. What remains on the grant is
what was granted, less what had been spent at the last accounting, less
everything on that stream.

## The other quarters

`checkout-capacity-2026q4`, `dispatch-capacity-2027q1`,
`lookup-capacity-2027q1` and `payments-capacity-2026q4` are queued on their own
grants with their own terms, and the same notebook produces their readouts.
