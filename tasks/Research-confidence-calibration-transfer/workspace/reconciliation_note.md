# Where a review outcome comes from

Written by the listing review desk for anyone reading the intake log.

## The outcome column

`review_outcome` is filled in when an adjudication on that listing closes, and
`outcome_closed_date` is the day it closed. Until then both cells are empty.
Nothing else writes to either column.

## Web and mobile

A listing on the web or mobile path is adjudicated here. The desk works the
day's file the morning after and closes it within a day or two, so
`outcome_closed_date` on those rows is one to three days after intake.

## Partner feed and reseller import

The desk does not adjudicate these itself. Their outcomes arrive on the
partner's reconciliation file, which lands every Friday. Each file closes the
listings the partner has worked through by then: for the feed that is the
listings opened up to six weeks before the file, and for the reseller import up
to a month before it. Both reach back to the previous Friday boundary, so every
`outcome_closed_date` on those two channels is a Friday.

The last file to land before this export was cut was the one on 28 August.

## Out of band

The adjudication desk will take a batch off the intake log directly and work it
out of band, which is what the credits in `audit_capacity.md` buy. A batch
names one cell — one channel and one intake plan — and the listings it returns
come back with `review_outcome` filled in on the receipt, oldest intake first. The desk writes `audit_receipts.json` and nothing
else does.
