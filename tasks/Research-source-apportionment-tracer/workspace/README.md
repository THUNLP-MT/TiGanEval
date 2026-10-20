# Block A header — January apportionment

Estates energy management. Everything the January report runs on is in here,
together with the collection agreement the desk works to and the notes from
each working session the window has had.

## What is here

- `header_context.json` is the window as the estates office publishes it: the
  window's first and last day, the three supplies, the characterisation sheet,
  the analyser's dwells, floors and repeatability, the weather log, the heat
  meter, the sample sheet, the operations log, the collection agreement's terms
  and what the director asked for.
- `header_samples.csv` is one row per slot the analyser has drawn: the sample
  id, when it was drawn, the point, the two channels, the marker's flag and the
  dwell. A marker under the floor for its dwell prints `<1.0` with the flag on
  it.
- `signature_sheet.md` is the characterisation of the three supplies at their
  own points, with the day it was read and the weather on that day.
- `analyser_manual.md` is the unit's operating note: channels, dwells,
  repeatability, the reporting floors and the sampling points.
- `weather_log.csv` and `heat_meter_daily.csv` are the site's own daily
  records, running from the first of the window to the last day the desk will
  serve a round on.
- `operations_log.md` is what the plant room left on the board in January.
- `service_agreement.md` is the terms estates and the analyser desk signed: the
  grant, what a slot costs, what a visit may ask for, the access list and what
  happens to a round the desk hands back.
- `report_request.md` is the director's note.
- `project_records/` holds the four working sessions this window has had, each
  with the author's notes and the evidence as it stood that day.
- `sample_ledger.json` is the visit receipt stream, written by the analyser desk
  and not by the notebook. What this window has been charged for is in there and
  nowhere else.
- `protocol.py` travels with the estates reporting stack: it is how the stack
  calls a notebook and how it reads the answer back, so it is not ours to
  change.
- The two files this team owns are `analysis.py` and `support.py`.
  `analysis.py` is the report as it runs today: the sheet read against every
  header slot, the slots averaged, the spread between them as the range, and a
  next visit that asks for more header slots. `support.py` has nothing in it
  yet.

## What the stack expects back

`analyze(context, ledger)` returns the report and `next_collection(context,
ledger)` returns the next visit to send the contractor on, or `"stop"`.
`protocol.py` documents both. The same file runs the other windows on this
stack.

## Tools

- `run_project(action="status")` prints the window, the agreement's terms, how
  many slots are spent and left, every visit on the ledger and the working
  sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's author ran it — the evidence as it stood on
  the day, the visits charged by then — and prints the session's notes, that
  day's rows and whatever the notebook handed back.
- `run_project(action="collect", point=..., channels=[...], dwell_min=...,
  samples=..., call_id=...)` sends the contractor out once. It returns the
  desk's receipt, appends it to `sample_ledger.json` and spends the slots.
  Sending the same `call_id` again returns the same receipt without spending
  anything.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the analyser desk, and
  nothing it writes is kept.
