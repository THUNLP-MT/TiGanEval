# Standing-score offer runs, Northgate

Operating notes for the weekly run. Kept by the growth desk; platform holds the
job itself.

## The run

Monday morning, ten weeks from 2 March. The run scores every account that was
active in the week before it and writes `run_status = scored` against it. An
account that was not active that week is carried forward with
`run_status = carried`: the run does not score it and no offer goes out to it.
It comes back into the next run if it is active again.

An account the run scores at or above **61.0** gets the offer that morning, and
`offer_flag` is set to 1 against it with the day in `offer_date`. Below 61.0 the
account is scored and passed over, and `offer_flag` stays 0.

## Credits

Account managers file a credit against an account before their run's Friday
cut-off. A credit is worth at most **1.00** points and goes into the score the
Monday run reads. The amount filed is kept in `credits_filed` on the register
row, and the score in `standing_score` is the one the account carries after it.

## Refreshes

Platform recomputes standing for part of the book when the modelling team ships
a new build. Two batches went out this window, **R-1 on 3 April** and **R-2 on
9 April**. `recompute_log.csv` carries one row per account each batch touched,
with the batch, the day and the score the account carried before it. The
register keeps the recomputed number from the day the batch lands.

## Columns

`offer_register.csv` is one row per account:

- `account_id`, `run_week`, `run_status`
- `standing_score`, the score the register carries today
- `credits_filed`, the credit a manager filed against the account
- `offer_flag`, `offer_date`
- `first_order_date`, the first order the export carries for that account after
  its run; blank when the export carries none
- `last_observed_date`, the last day the export watched the account
