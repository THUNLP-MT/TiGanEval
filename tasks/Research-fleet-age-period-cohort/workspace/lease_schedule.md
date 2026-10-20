# Ryecourt lease schedule

What the region leases its panel vans on. The lease reference on each row of
`van_register.csv` says which schedule that van runs under.

## L-36 — thirty-six months

The standing schedule. A van is allocated to a depot when it is built, handed
over to the depot six to twelve weeks later, and goes back thirty-six months
after it was allocated. The leasing company collects about twelve weeks after
the hand-back and the van stays on the depot's books until it does.

## L-14 — fourteen months

Taken for the 2022-H2 order only. Finance would not carry a full term against
that year's capital plan, so the whole of that build went out on a fourteen-
month schedule and went back at fourteen months. Same allocation and hand-over
terms; same collection window.

## Standing terms

- Mileage and damage recharges are settled at collection and do not appear on
  the fault log.
- A van that transfers between depots keeps its schedule and its hand-back date.
- The roster in `depot_roster.csv` is the depot's own headcount: a van is on it
  from allocation until the leasing company has collected it.
