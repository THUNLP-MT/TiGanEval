# Cell cycle-life study

This is the test lab's notebook for the HX-22 cycle-life campaign. Cells go on
to the channel tester in fixtures of four, run until their capacity falls away,
and the tester writes a capacity check every fifty cycles into its export. The
notebook turns those exports into the numbers the qualification programme asks
for.

- `study_notes.md` is the programme's own note: what the campaign is for, how a
  cell is retired, what the September build needs before it changes anything,
  and what the lot certificate guarantees.
- `project_records/` holds the operator's sheet for every session already run
  and the scheduler's booking sheet.
- `session_receipts.json` is the tester's own ledger. One entry per session the
  campaign paid for, each carrying the capacity checks of every cell in it. The
  tester writes this file and nothing else does.
- `protocol.py` says how the notebook's two answers are read. It ships with the
  lab's reporting tooling, so it stays as it is.
- `analysis.py` is the notebook as it stands: `analyze(context, receipts)` and
  `next_collection(context, receipts)`. It and `support.py`, which is empty,
  are ours to change.

## The bench

- `run_project(action="status")` prints the rack and each bay's setpoint, the
  firmware the tester is on today, the booking balance, the records, and every
  session the campaign has paid for.
- `run_project(action="replay", record="project_records/<name>.json")` opens one
  record, prints the tester's export behind it and what `analysis.py` returns
  for the study as it stands.
- `run_project(action="collect", bay=..., protocol=..., cells=..., request_id=...)`
  puts a booking on the tester now. It runs the cells, spends channel hours from
  the balance and appends the session's receipt to `session_receipts.json`. It
  cannot be undone, and asking again with a request id that already ran returns
  that session instead of running another one.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace, so you can read the exports, try arithmetic
  and check your own reasoning. Files it writes are discarded and it does not
  reach the tester.

## What is handed over

The programme office wants the September call, and the lab wants a notebook the
operator can keep using. The lots after HX-22 arrive with their own racks, their
own booking sheets and their own sessions, and the same two functions are run
on them without being rewritten each time.
