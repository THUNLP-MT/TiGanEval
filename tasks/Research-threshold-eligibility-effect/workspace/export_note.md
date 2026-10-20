# Ordering export, Northgate window

From: Devin Osei, data platform. 26 May 2026.

The ordering export for this window runs from 2 March and **stops on 24 May**.
It is a ninety-day window on the calendar but the export itself closes six days
before the end of it; the platform's next extract job takes over from there and
lands in a different table.

Orders land in the export **two days after they happen**. The pipeline batches
overnight and the reconciliation pass runs the following night, so an order
placed on the 22nd is written on the 24th and an order placed on the 23rd is
not in this export at all.

`last_observed_date` on each register row is the last day the export watched
that account: whichever comes first, sixty days after the offer or the last day
an order could still have been written. `first_order_date` is blank when the
export carries no order for that account inside that stretch. Nothing is
back-filled once the export stops.

For the council readout, account-days are the exposure behind each side's
ordering rate. Read orders per account-day back as the share of accounts that
would order at least once during sixty days. Multiplying a daily rate by sixty
counts orders over that span; it is not the requested share of accounts.
