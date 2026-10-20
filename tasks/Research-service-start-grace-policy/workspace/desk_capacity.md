# Northfield desk: the review's booking sheet

Agreed 2 January 2026 between support operations, the managed-support review
panel and finance.

## The grant

240 engagement slots for the quarter, for weeks the desk serves under a booking
rather than under its ordinary routing. The grant does not roll over.

- The desk serves at most 40 slots in one week.
- The desk holds at most 60 percent of a booked week's flags for the next open
  slot. The rest are started the day they are flagged.
- A slot is charged when the desk accepts the week.
- A week the desk hands back is charged 10 slots: the board is held open and the
  engineers are already rostered.
- The smallest week this review books is 10 slots. Below that the roster costs
  more than the week is worth, so the grant stops rather than buying one.

`booking_receipts.json` is the desk's own record of every week called for and
what it charged. The notebook does not write it.

## Naming a segment

A booking names the part of the desk's book it applies to. The sheet takes:

- `all`
- `plan_tier=standard`, `plan_tier=premier`
- `error_rate_7d=0.5`, `error_rate_7d=0.8`, `error_rate_7d=1.1`,
  `error_rate_7d=1.5`
- the two joined with a comma, for example
  `error_rate_7d=1.5,plan_tier=premier`

A segment with no flags in the week comes back with nothing served and is
charged as a week handed back.

The desk serves the next open week. A `week` on the call is the week you mean
and is carried onto the receipt; the desk serves the next open one either way.

## The book

`desk_book.json` is the monthly count of the accounts Northfield carries, by
seven-day error rate and plan tier, taken on the first day of the window. It is
the book the panel priced the desk against.
