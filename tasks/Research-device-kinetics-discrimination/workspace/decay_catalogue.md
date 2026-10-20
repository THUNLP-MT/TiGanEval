# Decay catalogue, EM-9 and the families behind it

Maintained by reliability. Four laws are carried for this emitter family. Each
one says what share of a module's output has gone after a given amount of
accumulated soak, and each carries the two stress terms it was calibrated with
on the field ladder years ago.

Accumulated soak for a module held at a drive and a case temperature is its
wall-clock hours multiplied by the law's own drive factor and by its own
temperature factor. The field drive and the hold the campaign is written
against are in `soak_context.json`; at those settings both factors are one.

| field name | loss after `h` hours of accumulated soak | drive factor at `I` amps | factor per ten degrees over the hold |
| --- | --- | --- | --- |
| `defect_growth` | `a · h^0.66` | `exp(2.1993 · (I − 1.4))` | 1.7 |
| `interface_creep` | `a · ln(1 + h / 760)` | `(I / 1.4)^3.4` | 3.4 |
| `contact_oxide` | `a · (1 − exp(−h / 400))` | `(I / 1.4)^3.4` | 2.2 |
| `drive_fatigue` | `a · h / 1000` | `exp(2.1993 · (I − 1.4))` | 1.3 |

`a` is the one number a law leaves free. It is a property of the build rather
than of the catalogue.

For a campaign review, reliability fits that one number by least squares in
the meter's milliwatts over the module rows the report counts. The fit is then
read one drive-and-case setting at a time, never by pooling settings: a setting
decides only when it has at least eight counted rows. A law remains standing
only when the root-mean-square residual at every deciding setting is no more
than half again the meter's repeat spread and the fitted law reaches the target
loss at the field settings. The report uses the arithmetic mean of the
target-life answers from the laws that remain standing as its life figure.

The same four constants travel with every campaign in
`soak_context.json`'s `catalogue`, and reliability re-issues them per family:
the shapes carry over, the constants do not.

## Where they came from

All four were fitted against the same field ladder, which ran at 1.4 A and
1.7 A. Nothing was ever run below 1.4 A or above 85 °C on that ladder, and the
shop has never had a build that settled the argument between them.

## What the catalogue does not say

Which law a build follows. Reliability has argued about EM-9 since the family
opened. The February review minute records the argument as open.
