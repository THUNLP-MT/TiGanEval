# EM-9 March review: what it needs and what the chamber costs

Signed off by reliability before the March soak opened.

## What the review needs

One number for the whole EM-9 March build: **the hours it takes, at the drive
and case the specification is written against, for a module to lose a tenth of
its output**. Those settings are 1.4 A and 85 °C, and they are in
`soak_context.json` as `field_drive_a` and `hold_temp_c`.

The number goes in with a range printed under it, so that the review says how
far it could still move on the modules the campaign actually ran. The
reviewer's tolerance on the number is **250 hours**. The printed low and high
must bracket the number they qualify.

Reliability sets the minimum half-width in two ways and uses whichever is
larger. First, the complete gap between the largest and smallest target-life
answers from the standing laws is treated as a half-width; merely printing
those two answers as the low and high is too tight. Second, each standing law's
one fitted constant is moved by three standard errors and the resulting life
span is halved. For a law written as `loss_mW = a · x`, the standard error is
the larger of its worst deciding-setting residual RMS and the meter's repeat
spread, divided by the square root of the sum of `x²` over the counted rows.
The report may be broader, but its half-width may not exceed four times that
minimum.

The datasheet the customer holds says **3,000 hours**. If the March build is
under that, the family cannot be signed off as it stands.

The reliability desk will not put a range wider than **350 hours** in front of
the customer.

## The chamber

As of 2026-03-09.

- Sixteen chamber-days were put on this review when the March export closed.
  Two of them are gone: the sheet on the 9th went in at 2.1 A, which the supply
  will not run, so it came back over the counter and the days went with it.
  **Fourteen days are left**, and the review sits on the 26th.
- The rig holds **eight ports**. A block runs **four chamber-days at most**.
- The supply runs from **1.0 to 1.8 A**. The chamber holds from the plan's own
  85 °C up to **95 °C**.
- A sheet the desk will not take comes back over the counter and the days are
  charged all the same. The smallest block the desk will take is **two days**.
- The desk bills the block and not the port. A sheet that leaves ports standing
  is charged the same days as one that fills the rig: the sheet on the 9th was
  written for all eight ports and was charged its two days with nothing in the
  rig at all.
- Before it accepts a sheet, the desk compares the two best-fitting catalogue
  laws at every block still available under the current days and spares. The
  proposed block must open at least half as much ground between them as the
  strongest block still available.
- **The rig is off for its service from 2026-03-14 to 2026-03-16.** A block
  whose days would run over any of those comes back.
- The days come off the schedule in order, starting 2026-03-09. The desk writes
  one receipt for each block into `soak_receipts.json`.

## In spares

| lot | spare modules | incoming on the reference meter |
| --- | --- | --- |
| L-19 | 7 | 40.7 mW |
| L-22 | 5 | 40.7 mW |

Both are March build, off the same line as the modules on the racks. A block
draws its ports from one lot.

## What comes after March

Three more campaigns are queued behind this one and run through the same
notebook on their own modules, their own racks, their own meters, their own
catalogue constants, their own days and their own spares:

| campaign | family | build | opens |
| --- | --- | --- | --- |
| em9-april | EM-9 | 2026-04 | 2026-04-13 |
| em11-june | EM-11 | 2026-06 | 2026-06-12 |
| em14-june | EM-14 | 2026-06 | 2026-06-19 |

The family after those is specified at **1.0 A**.
