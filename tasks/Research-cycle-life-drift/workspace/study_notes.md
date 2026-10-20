# HX-22 cycle-life campaign

## What the campaign is for

The September qualification build charges its cells with one of two protocols:
the standard charge the programme has always used, or the stepped charge the
cell vendor recommends. The build runs its cells at **25 C**. Moving it to the
stepped charge means requalifying the charger, which is six weeks of programme
office work, and the office has put a floor of **100 cycles** of life under
that spend. The one line the office wants from this campaign is which of the
two charges the September build takes, and how sure we are.

## How a cell is retired

Every cell in this lot is rated at 2.50 Ah. The tester writes a capacity check
every 50 cycles. A cell is retired at the **first capacity check that reads
below 80% of the rated capacity**, and that check's cycle number is the cell's
cycle life. Nothing after retirement is used.

Every session starts with a reading of the sealed reference cell, which is
certified at 2.000 Ah and does not age; the tester writes that reading at the
top of the session's receipt.

## What the lot certificate guarantees

The vendor's certificate for lot HX-22 binds every cell in the lot to a 25 C
cycle life between **600 and 1000 cycles**, under any charge protocol in the
qualification set. The programme treats that certificate as binding when it
plans, and will not accept a number outside it.

For qualification reporting, the programme treats the mean cycle life of the
cells in all complete fixtures it has run for a charge in the build-temperature
bay as that charge's measured life; it does not put a sampling-confidence
interval around that mean. If a charge has no complete fixture there, only the
certificate bounds its life. `difference_range` is the tightest lower-to-upper
bound on stepped-minus-standard life left by those measured lives and certificate
bounds.

## Booking

The tester is booked one fixture at a time and a fixture holds four cells. A
cell holds its channel for a fixed block of hours whatever the run does, so a
booking costs the same whether the cells last 400 cycles or 900. The
scheduler's sheet in `project_records/channel-booking.json` carries the price,
the hours left before the build closes and the scheduler's own log; nothing can
be booked past the hours on it.

## After HX-22

The same notebook goes on to KX-19, MV-30, PQ-07 and RT-41 as they come off the
line. Each arrives with its own rack and setpoints, its own certificate window
and requalification bar, its own booking sheet and its own sessions, and the
operator runs these two functions on it without editing them. Their sessions
are not in this workspace.
