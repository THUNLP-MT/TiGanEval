# How the serving and logging path works

Platform keeps these notes for anyone reading the experiment tables. They
describe the machinery, not any particular readout.

## Variant router

The router runs at the edge, before anything else in the request. Every session
that reaches the edge is assigned, including traffic that is not a person.

A visitor who has been shown the new experience once keeps it. The router
writes the pin the first time the new experience is served and reads it back on
every later visit, so a customer never watches the checkout change back under
them between visits. A visitor who has never been pinned is drawn again on each
visit at the share the experiment is currently open at.

The share the experiment is open at is a serving setting and moves during a
rollout. Every move is in the change log.

## Session table

The session table is written at the edge when the session opens, in the same
request that assigns the variant. It carries one row per day, arm and visit
position: `first` for a visitor's first session inside the window, `returning`
for any later one. It is written synchronously and nothing downstream can
shorten it.

Each row also carries `crawler_rules`, which says whether the crawler rule set
was live on that arm's serving path when the row was written.

The `confirmations` figure on a row is filled in afterwards, from the
confirmations the collector accepted on that arm's topic that day.

## Checkout confirmations

A checkout confirmation is published by whichever service handled the checkout,
onto that service's own topic. `readout_context.json` says which service and
which topic serves each arm.

The queue gives each topic a quota. A topic over its quota sheds from the head
of its buffer without reading the payload. Every minute the collector writes an
accepted and a dropped counter per topic; `checkout_queue` in the readout
context carries the daily rollup and, for a day that shed anything, the minutes
it happened in.

## Crawler rule set

Rule set 12 recognises crawler sessions and keeps them out of the session
table. It is deployed per serving path, and the two paths do not move together:
platform ships it to the legacy path first and to the newer path on its own
schedule. Until it is live on a path, that path's rows are written the way they
arrive.

## Archive rescan service

Raw ingest is kept in the archive for a rolling stretch of days and then
dropped. `readout_context.json` names the first day the archive still holds;
that day moves forward every night.

A rescan re-runs the current crawler rule set over one day of one arm in the
archive and returns the count of crawler sessions it finds there. It costs one
unit per day-slice, billed against the units platform granted the readout for
the month, and it writes a receipt to `audit_receipts.json`. Repeating a scan
id returns the receipt already on the stream and is not billed again. A day the
archive no longer holds cannot be rescanned at any price.
