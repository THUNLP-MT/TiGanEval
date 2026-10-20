# The three bundles on test

Vendor cards as they came with the drop, plus what our own release engineering
recorded about each pool. `bundles/score.py` is the scorer itself and
`bundles/cards.json` holds the weights; both ship with the drop and neither is
ours to change.

## mallow

Front end holds the three reflectance windows to a span of 1.45 before the rule
sees them; anything above that span reaches the rule as 1.45.

Tuned on 214,000 captures from lit counter positions across eleven retailers.
The vendor's own card quotes 96.8 per cent on that pool.

## thistle

Front end passes the eight columns through untouched.

Tuned on 180,000 captures the vendor describes as a mixed indoor pool. The card
quotes 95.1 per cent.

## rowan

Front end passes the eight columns through untouched, and the rule leans away
from brightness: the reflectance weights are the smallest of the three and the
contrast weight is roughly a third of mallow's.

Tuned on 96,000 captures from what the vendor calls dim and damaged label work.
The card quotes 93.4 per cent, and the vendor's release engineer said in the
call that the pool was the hardest of the three they built.

## What the vendor's numbers are not

Each percentage above is on that vendor's own pool. None of the three pools is
Harrowgate, and the three pools are not each other.
