# Inline analyser AT-24 — operating note

The unit sits on the header main and reads one slot at a time. Two channels
ship with it; a third is available on the hire module.

## Channels

- **Conductivity index**, µS/cm. Reads on every slot.
- **Leak-trace marker**, mu/L. Reads on every slot.
- **Pump-ripple index**, arbitrary units. Only with the hire module fitted. The
  module reads the header and each plant's own pump set in the same pass and
  prints all four figures on the receipt. No dwell floor applies to it.

## Dwell

The unit runs a slot at five minutes or at thirty. Thirty minutes counts as two
slots against the collection agreement.

| Dwell | Conductivity repeatability (µS/cm) | Marker repeatability (mu/L) | Marker reporting floor (mu/L) |
| ---: | ---: | ---: | ---: |
| 5 min | 6.0 | 0.12 | 1.0 |
| 30 min | 2.5 | 0.035 | 0.2 |

Repeatability is one standard deviation between slots drawn back to back on the
same stream. The pump-ripple channel repeats to 0.6 units at either dwell.

## The marker floor

The marker channel integrates counts over the dwell. Below the floor for that
dwell the unit has not accumulated enough counts to put a figure on the sheet,
and prints `<1.0` at five minutes or `<0.2` at thirty. The printed line carries
`mark_flag = floor` and the floor itself in `mark_floor_muL`.

## Sampling points

The unit draws through the sample loop and the desk selects the point. The
header, both plant rooms and the east riser are plumbed to the loop. Anything
else needs a temporary tap and is not on the access list.
