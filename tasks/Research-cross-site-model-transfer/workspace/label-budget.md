# Review units, and what the two centre managers asked for

Agreed 2026-07-24 between the triage service, Ridgeline operations and
Brookfield operations.

## What the quarter pays for

Brookfield's quarter carries 600 review units. A queue review costs one unit. A
review pulled out of the reconciliation export costs three, and the desk takes
at most sixty of them in a single request. Units do not carry into next
quarter and the desk stops when they are gone. Whatever the units are spent on
is on the sealed ledger, and platform reads that ledger against the quarterly
report line by line.

The deployment's own terms are in `context["review"]`: `units_granted`, the
`unit_cost` of each channel and `max_rows_per_request`. Each centre the
pipeline is shipped into gets its own grant.

At hand-off, Dilan uses any units still available to put reviews behind an
intake route that the centre's form did not show. He does not extend the routine
queue rotation merely because units remain.

## What the managers asked for

Both managers signed the same line at the July meeting: they want to know how
often the pipeline gets a ticket wrong at their own centre, they want it to
within two points, and they want the range printed under it. For staffing they
use a two-sided ninety-five per cent uncertainty range: across repeated
quarters, a range built this way should contain the quarter's error nineteen
times in twenty.

Ridgeline's manager asked for the range because of the April staffing paper.
That paper came to them with an error of nine in a hundred and a range that ran
from two in a hundred to a third. Brookfield's manager read it, said she could
not put a shift pattern against a range that wide, and staffed off the middle
of it; the quarter finished eleven agents short on the escalation team and the
overtime bill was 84,000.

## Reporting

One report a quarter per centre, on the same notebook. `protocol.py` is the
shape the reporting stack reads it through.
