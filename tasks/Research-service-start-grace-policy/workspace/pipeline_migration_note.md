# Eventing migration and the escalation export

Platform note, 26 March 2026. Written by Kofi Anand, platform eventing.

## What moved

The escalation stream moved onto the new eventing platform on 24 March 2026.
The old topic stopped accepting on that date and the reporting export that
`flag_ledger.csv` is built from reads the old topic only.

An escalation record is written two days after the incident desk opens the
escalation, when the shift review closes it. So the last incident the export can
carry is one opened on 22 March.

`last_observed_date` on a flag row is the last day the export can speak for that
flag: twenty-eight days after the flag, or 22 March, whichever comes first. On a
row flagged after 22 March it is that row's own flag date.

## Rebuild

The new platform carries the same fields and no lag. Rebuilding the export off
it for the window before the migration needs the old topic's archive, which
Amber has asked storage to restore. No date yet.

Until then, anything the desk books runs on the new stream, where the two-day
shift review still applies: the rows a week booked now comes back with stop two
days earlier than they otherwise would.

## Actions

- Storage to quote for restoring the old topic's archive. Owner: Amber. No date.
- Support ops to note the cut on any readout that reaches the quarterly review.
  Owner: Rhea. Due 5 April.
