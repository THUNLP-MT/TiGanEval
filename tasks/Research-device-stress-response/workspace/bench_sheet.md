# Bench sheet, QR-40 March qualification

Filled in by whoever is on the bench, one block per batch.

## Batches

| batch | bench | date | hold (min) | cartridges | couplings |
| --- | --- | --- | --- | --- | --- |
| B-01 | B-1 | 2026-03-04 to 2026-03-06 | 30 | all six | 360 |
| B-02 | B-1 | 2026-03-09 to 2026-03-11 | 5 | all six | 1080 |
| B-03 | B-2 | 2026-03-16 to 2026-03-18 | 30 | C-255, C-275, C-300 | 180 |
| B-04 | B-2 | 2026-03-23 to 2026-03-25 | 30 | all six | 360 |

## Consoles

Both benches read through a transducer with the sticker on the front of the
console. Both stickers say **203.0 bar**. The console writes what the
transducer gives it, to one tenth, into the `reading_bar` column.

`B-2` is out of service from **2026-04-12 to 2026-04-15** for its annual
transducer swap. Nothing runs on it in that window.

## Dead-weight block

`DWB-200` is the shop's dead-weight block. It is one part, certified at
**200.0 bar**, and it goes on the bench at the start and the end of every
batch. Its rows go into the run table like any other row, with `DWB-200` in
the cartridge column and `block` in the result column.

| batch | bench | block at the start | block at the end |
| --- | --- | --- | --- |
| B-01 | B-1 | 199.1 | 201.5 |
| B-02 | B-1 | 201.5 | 199.1 |
| B-03 | B-2 | 185.2 | 182.8 |
| B-04 | B-2 | 182.8 | 185.2 |

## Notes from the batches

- **B-01.** Ladder run twice through, six cartridges, sixty couplings each.
  C-255, C-275 and C-300 all came back at 203.0 on every unit.
- **B-02.** The whole production batch went through this one, a hundred and
  eighty couplings a cartridge. Sanne: "held 5 min, bay wanted at four."
- **B-03.** Bench 2 was the one free that week. Only the top three cartridges
  went on it; the shop was short of the low sizes until the 23rd.
- **B-04.** The rest of the ladder on bench 2. C-255, C-275 and C-300 came back
  at 203.0 here as well.
