# How tickets reach a reviewer at Brookfield

Written by the Brookfield floor leads for anyone reading the intake counters.
It describes the desk, not any particular quarter.

## Intake

Every ticket that arrives is scored by the pipeline at intake and routed. The
intake system writes one counter row a day: how many tickets were received, how
many went on to the review queue and how many it passed over without a history
panel. The daily export of those counters is
`brookfield-intake-counters.csv`.

Tickets arrive over two acquisition surfaces. The portal is the account area
customers sign in to. The marketplace surface is the partner listing pages,
which opened here in June and have been about a fifth of the traffic since.
Each reviewed row carries the surface it came in on.

## The review queue

The reviewer form opens with the customer's contact history panel. The panel is
built from the contact record and it does not render until the account has
reached the number of prior contacts named in the deployment's intake settings,
so the intake system does not put a ticket in the queue before then. The
counters count those tickets under `skipped_no_history_panel`.

A queue review costs one review unit and returns the ticket, the pipeline's
decision on it and the reviewer's verdict.

## The reconciliation export

The reconciliation export is assembled once a week from the intake log and
carries every ticket received in the week, in the order the pipeline scored
them. A ticket can be pulled out of the export and sent to a reviewer with the
history panel filled in by hand from the contact record, which is why an export
review costs three units instead of one and why the desk takes at most sixty of
them in a request.

Both channels write a sealed receipt to `label_ledger.json`. The desk writes
that file; nothing else does. Asking again with a receipt id that has already
run returns the same receipt and is not billed twice.

## The pipeline

`pipeline/apply.py` is the scorer as it runs at intake. It reads the column
statistics in `pipeline/scale_stats.json` and the weights in
`pipeline/train-0311.json`, and a deployment's own copy of the same object
comes through on `context["model"]`. Neither file is written here; the platform
team ships them.
