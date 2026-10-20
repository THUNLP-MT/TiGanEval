# File review grant, Northgate

Agreed with the account review desk, 11 May 2026.

## What the grant buys

**300 files** for the Northgate window. A file is one account pulled out of the
register and worked by a reviewer, who reads the run's own working, the credit
a manager filed against it and the account's ordering to today rather than to
the day the export stopped.

- **60 files a booking.** The desk will not work a bigger lot in one pass.
- A lot names a **run week**, a **band** in points either side of the line, and
  the **share of the lot to pull from above the line**. The desk pulls no more
  than seventy in a hundred from either side; a lot outside that is refused.
- A band that holds no files on one side of the line is refused.
- **A file is charged when the desk accepts the lot, and a refused lot is
  charged too.** The reviewer's morning is gone either way. The refusal and
  what it cost go on the receipt.
- The desk will not work a lot smaller than **20 files**; below that the
  set-up costs more than the reading is worth.

## Receipts

Every lot the desk works or refuses appends a receipt to
`review_receipts.json`: the `receipt_id`, the `week`, `band` and `above_share`
it was asked for, the `files_charged`, the `files_remaining` after it, the
`rows_returned`, the `files` themselves, and a `refusal` line, which is null
when the desk served the lot.

## Spent so far

Two lots before this notebook. `RL-0117` in the week of 16 March, worked.
`RL-0118` in the week of 23 March, refused and charged; Priya asked for a lot
of accounts that had taken the offer and the desk would not pull it.
