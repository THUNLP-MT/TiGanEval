# Quote platform capacity review — 24 September 2026

Standing item, monthly. Attending: quotes platform, platform infrastructure,
finance.

## What was asked for

Four more quote instances, at 2,400 euro a month each, 9,600 a month in total.
The ask was made on the strength of the week the dashboard drew: the daily
error percentage on `/v1/quote` opened the window at 4.85 and reached 11.38 on
the 23rd, and the on-call pager went off on the evenings of the 22nd and the
23rd.

## What finance said

Refused, pending a number the review can stand behind. The minute records the
objection as put: the instance line has grown 41 per cent this year against a
quote volume that has grown 6, and the last two capacity asks were carried on
the same dashboard reading. Finance will look again when the review brings a
figure with a range around it that it can put its name to, and not a percentage
read off a chart. They were equally clear that neither end can assume away
something the review has not settled or leave room for something its records
have already ruled out.

## Edge trace units

Platform infrastructure grants each review twelve edge trace units a month, one
unit per pool-minute pulled, and they do not roll over. Five are spent on the
September review. The edge archive keeps raw pool rows for 72 hours and drops
the rest every night, so a minute that has aged out cannot be pulled at any
price and a unit spent on it is a unit gone.

## Reviews on this notebook

The same notebook runs the review every month. The August week is on the
platform share drive; the October week and the November week are due after this
one. Each has its own week and its own client and pool state, and infrastructure
will not sign off a notebook that has to be edited between them.

## Actions

- Quotes platform to bring the September number and a range to the October
  review.
- Finance to hold the instance ask open until then.
