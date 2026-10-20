# The audit night budget

Signed off by the regional service manager on 2026-06-26, for the month in
hand. Each depot in the region carries its own grant and its own roster.

## What the month pays for

- Halstow's grant is 36 audit units. Units do not carry into next month.
- A night visit costs 3 units and times up to 6 jobs of one class. An accepted
  night uses the same units and roster slot however many jobs are requested,
  so the regional office requires every accepted booking to use all 6 places.
- The desk runs at most 2 night visits in a week.
- A request the desk turns away still costs 1 unit: the crew is rostered and
  stood down, and the unit is charged whether or not a job is timed. Asking for
  a class outside its rostered weeks, asking for more jobs than a night takes,
  asking on a week that already has its two nights, or asking with less than a
  visit's worth of the grant left are all turned away and all billed.
- The desk stops when the grant is gone. A month that ends with units in hand
  and nothing worth spending them on is a normal month.

The depot's own terms come through on `context["visits"]`: `units_granted`, the
`units_per_visit` and `units_per_refusal`, `jobs_per_visit`, `visits_per_week`,
the `weeks` the crew is out, and the `roster`.

## The receipts

`visit_receipts.json` is the desk's sealed record. The desk writes it; the
notebook cannot. Every request the depot was billed for is on it once, with the
week and class it was booked on, how many jobs were asked for and how many came
back, what it was charged, whether the class was on the roster, the reason it
was turned away when it was, and the units left after it. The regional office
reconciles the grant against that file line by line before it releases the next
month's units.
