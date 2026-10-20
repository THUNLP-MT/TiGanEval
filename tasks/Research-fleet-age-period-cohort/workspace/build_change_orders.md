# Ryecourt build change orders

Programme engineering's change-order file for the panel van. An order that was
taken up carries the build month it took effect in; the line ran to the sheet
before it until then. `build_sheets.csv` carries the body spec and the lot
numbers each build month actually ran on.

## Taken up

| Order | Effective build month | Body spec | Change |
| --- | --- | --- | --- |
| CO-100 | 2021-02 | BS-5 | floor pan gauge |
| CO-107 | 2021-10 | BS-6 | rear door seal |
| CO-114 | 2022-07 | BS-7 | loading bay lamp |
| CO-121 | 2023-01 | BS-8 | front hub carrier |

## Raised and not taken up

| Order | Raised | Status |
| --- | --- | --- |
| CO-103 | 2020-11 | withdrawn by the supplier, no build month affected |
| CO-109 | 2021-06 | deferred to the next platform, no build month affected |
| CO-111 | 2021-12 | superseded by CO-114 before release |
| CO-116 | 2022-05 | held at the depot trial stage, never released to the line |
| CO-118 | 2022-09 | raised against the Marbeck body shop, not this programme |
| CO-124 | 2023-05 | raised after the last build month in this file |

## Notes

Body spec and lot numbers move together: the line draws from one set of lots
until an order takes effect, and the sheets are re-issued on the day it does.
Programme engineering will not answer a query about a build month by the month
alone; quote the sheet.
