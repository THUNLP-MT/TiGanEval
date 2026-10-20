# Managed support: how a flag is routed

Owner: Northfield support operations. Last changed 9 February 2026.

## The routing bar

A flag carries the account's seven-day error rate at the moment it was raised.
The monitor reports that rate at one of four levels: 0.5, 0.8, 1.1 and 1.5.

A flag at or above the routing bar takes a same-day engagement slot. A flag
below the bar goes into the queue and waits for the next open slot. The row on
the ledger says which of the two the flag was put on, in `start_queue`.

The bar is a capacity setting, not a promise. Where the desk finds it has a free
engineer and nothing over the bar in front of it, it starts a queued account the
same day; where the day is already full, an account over the bar goes into the
queue with the rest.

The bar sat at 1.5 when Northfield opened and has moved twice since. Both moves
were headcount:

| From | Bar | Why |
| --- | --- | --- |
| 4 August 2025 | 1.5 | opening headcount |
| 3 November 2025 | 1.2 | two engineers added |
| 9 February 2026 | 0.9 | four engineers added, weekend cover ends |

## The grace window

An account the desk queues is to be started within six days of its flag. Beyond
that the queue is meant to hand it back to monitoring. Where the desk has
cleared its board it opens the engagement anyway, and the ledger carries those
late starts with the day each one opened.

An account that escalates is handed to the incident desk. Support does not open
a managed engagement on a flag once its account has escalated.

## Plan tier

`plan_tier` is the account's contract: `standard` or `premier`. Premier accounts
are worked by the named-engineer pool and standard accounts by the shared pool.
The tier is on every flag row and on the desk's own book in `desk_book.json`.
