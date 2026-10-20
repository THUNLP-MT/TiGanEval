# Node-hour grant — pretrain-sweep-2026-09

The window's own grant, separate from the hours the segments on
`run_ledger.csv` were run under. It pays for whatever the sweep books from here
to the end of the month.

| | node-hours |
| --- | ---: |
| granted for the window | 50 |
| charged so far | 8 |
| left | 42 |

Charges are the console's, not ours: `collection_receipts.json` is the record,
the console writes it, and nothing else does. A job that runs is charged the
hours it ran. A job the console turns away is charged one hour and comes back
with the reason on the receipt. The grant does not roll into October.

Charged so far:

| receipt | run | node | asked for | charged |
| --- | --- | --- | ---: | ---: |
| sweep-0912-a | cfg-01 | n-b | 6 hours | 6 |
| sweep-0913-a | cfg-02 | n-a | 12 hours | 1 |
| sweep-0913-b | cfg-04 | n-b | 20 hours | 1 |
