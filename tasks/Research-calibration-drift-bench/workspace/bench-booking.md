# Bench booking sheet, days 79 to 84

Signed off by the line scheduler on day 78. The procurement review is on day 85
and nothing runs on the bench after day 84.

## Campaign allowance

Twelve bench-hours were set aside for this campaign before the review. The rest of
the week on both rigs is booked to other work. A part session is two hours and
a block run is half an hour; the numbers in `bench_context.json` under
`booking` are the ones the console charges against.

| Day | Rig 1 | Rig 2 |
| --- | --- | --- |
| 79 | open, 4 h | open, 4 h |
| 80 | open, 4 h | open, 4 h |
| 81 | open, 4 h | out, fixture pin |
| 82 | open, 4 h | out, fixture pin |
| 83 | open, 4 h | out, fixture pin |
| 84 | open, 4 h | back on the bench, but the shift is the review handover |

Rig 1 has twenty-four hours open across those days and rig 2 eight, so rig 2
takes at most eight of this campaign's twelve. The console will not accept a
session that runs past any of those figures; `bench_hours_left` and
`rig_hours_available` in the booking block carry them.

## Parts

Whatever stores still holds, and nothing else. `stores-inventory.csv` is the
sheet; a part is worn once and cannot be run again. Purchasing cannot get more
parts out of either supplier before the review.

## Charging

Every session the bench runs against these hours writes a receipt to
`bench_receipts.json` with the hours it cost. The console writes that file; the
notebook cannot.
