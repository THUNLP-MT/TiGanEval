# Bench sheet, EM-9 March soak

Filled in by whoever is on the bench at each reading session.

## The meter

One bench meter serves both racks. The sticker on its front reads
**40.0 mW full scale**. It writes to a tenth of a milliwatt into the
`output_mw` column of the export.

Repeat spread on the same part, measured over the qualification's own repeat
checks: **0.10 mW**. That is the figure the desk quotes when anyone asks how
close two readings of the same part come.

## The reference source

`REF-20` is the shop's reference source, one sealed part held at **20.0 mW**.
It goes on the bench at the start of every reading session, on whichever rack
is being read, and its reading goes into the export like any other row, with
`REF-20` in the module column and the lot column left blank.

Recent sessions:

| date | rack | REF-20 read |
| --- | --- | --- |
| 2026-03-12 | R-A | 20.0 |
| 2026-03-14 | R-A | 19.9 |
| 2026-03-16 | R-A | 20.1 |
| 2026-03-20 | R-B | 19.9 |
| 2026-03-22 | R-B | 19.9 |
| 2026-03-24 | R-B | 20.0 |

The desk keeps these because a session whose reference read walks off 20.0 is
one the shop re-runs. None of March's did.

## Goods-in

Every module is read once on the metrology bench's own reference meter before
it goes on soak, and that reading is what `module_index.csv` carries in
`incoming_mw`. The metrology meter is a different instrument from the bench
meter and is not used again once a module is on the rack.

The twenty-five modules on March's sheet came in between **40.5 and
41.2 mW**.

## Reading sessions

Both racks are read on the same two-day cycle, so a module carries a bench row
every 48 hours from the day it went on. The bench does not touch the racks
between sessions; the drive and the case hold at what the plan sets.
