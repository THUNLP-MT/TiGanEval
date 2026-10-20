# Collection agreement — inline analyser, Block A

Between estates and the analyser desk, for the 2025/26 heating season. What the
desk will and will not do, and what it charges for.

## Slots

- The season's grant is **30 slots** on the Block A header. Slots do not roll
  over into the next season.
- A five-minute slot costs one. A thirty-minute slot costs two. Fitting the
  hire module costs two slots on top of the visit it is fitted for.
- **14 slots are left** at the close of the January window. `sample_ledger.json`
  carries what every visit so far cost.

## Visits

- A visit names **one point** and at most **four slots**. The contractor is on a
  round; he does not open two stations in a morning.
- The access list is the header, the tie-in plant room, the gas plant room and
  the east riser. Anything else needs a temporary tap and the desk will not
  take it.
- A visit the desk hands back over the counter is **charged all the same**. The
  round on 26 January went that way.
- The desk serves the January window's remaining rounds on 1, 2, 3, 4 and 5
  February — one round a day, and the days are gone once they are served.

## What comes back

Every visit gets a sealed receipt on `sample_ledger.json`: the call id, the
point, the channels, the dwell, the slots charged, the day it was served, the
slots left after it, and the readings, or the desk's line where the round was
handed back. The desk writes that file; nothing else does.
