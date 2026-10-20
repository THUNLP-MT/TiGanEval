# Device lab night runner

`harness/` is what turns a recorded session into a night on the benches. One
process runs it; there are no threads and no wall clock. Lab time is virtual
and moves only when a suite step says it spent time.

- `harness/protocol.py` ships with the bench controllers and is the same file
  on all eight of them, so it stays as it is. It owns the phase names
  (`lab_open`, `bench_open`, `case`, `bench_close`, `lab_close`) and
  `HANDSET_PHASES`; the `Handset`, `Execution`, `CaseRecord` and `Session`
  types; `load_inventory` and `load_session`; the cooperative `Scheduler`
  (`spawn`, `park`, `unpark`, `now`, `advance`, `run`, `outcome`); the
  `Ledger` and the `HandsetPool`; `LabError`, `suite_error`,
  `unbound_context` and `check_gate_request`; and `interpret`, which runs one
  phase program for one handset and writes every step down.
- `harness/sequencing.py` is ours: `SuiteRunner`, which decides what runs when.
- `harness/rendezvous.py` is ours too: `Gates`, sketched at the post-mortem
  and still a placeholder.

## How a night runs

`lab_open` runs once, then each bench in turn, then `lab_close` once. A bench
is `bench_open`, then every case in `case_order`, then `bench_close`. The
bench-wide phases run for the bench as a whole; a case is what runs on the
handsets themselves.

`lab_devices.json` is the lab inventory: every handset the lab owns, and the
bench it is wired to. The `bench` key is new. A session names only the
handsets taking part, so a bench can be three handsets on one night and one
handset on another, and `Session.bench_handsets` answers for the session in
hand rather than for the inventory.

A phase runs as a fiber: `Scheduler.spawn` registers it, `Scheduler.run` gives
turns until nobody can take one, and `Scheduler.outcome` says what a finished
fiber returned or raised. A fiber that yields keeps its place in the turn
order unless something parked it. Each fiber carries its own reading of lab
time; `Scheduler.unpark` moves a released fiber's reading forward to the
reading of whoever let it go.

## Lab operations notes

- **The pager rota.** A `SuiteError` and a `ValueError` page the suite author
  who wrote the case; a `LabError` pages the lab on-call, who goes and looks at
  the chamber. Getting that split wrong is how we spent a Sunday morning with
  the wrong person on the phone. `harness/protocol.py` is where the split is
  written down.
- **A night is worked to the end.** Whoever the rota pages reads the console in
  the morning, so nothing that goes wrong inside a night stops the rest of it.
  A case that ends badly costs that case: a handset that stops answering, and a
  line the bench controllers will not run at all, both leave the bench's later
  cases, the bench's closing and the benches behind it exactly where they were.
  A chamber that will not open costs that bench and no more. One mistyped
  deadline in one case ended the night of 12 February on the first chamber, and
  the three benches behind it never ran the week of a firmware drop.
- **A case group ends together.** If one handset execution fails while another
  is parked for it at a named point, the runner retires that case's open points
  and ends the unfinished executions as errors. The next case starts with new
  executions and new points; no waiter from the failed case remains parked.
- **The shared pool.** Handsets belong to the lab, not to a session. A bench
  takes its handsets out of the pool while it works and puts them back when it
  is finished; a handset still checked out in the morning is a handset the
  next night's session cannot get, which costs a second night rather than a
  test. The night of 4 August ended with six handsets locked and nothing ran
  the following evening.
- **The morning report.** The ledger is what the lab reads at eight o'clock to
  decide which unit goes back to the vendor and which bug gets filed. It has
  one row per case per handset, and the dashboard groups those rows by case
  name across nights, so the case name in a row stays the case's own name and
  the handset is a field on the row. Its outcome is `passed` when the execution
  completed without a flag, `flagged` when it completed with one or more flags,
  and `errored` when it raised or was cancelled because its case could not
  finish.
- **A named point in a case** is where the handsets working on that case are
  supposed to be at the same moment. The whole reason the handover suite
  exists is the window in which both handsets are live at once; if that window
  never happens the case measures nothing and the report still says green.

## Recorded sessions

`project_records/` holds four nights the lab replays before a change to the
runner goes out.

- `run_project(action="status")` lists the runner's files, the inventory by
  bench, and the four recorded nights with the handsets, benches and cases each
  one uses.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  night against the current workspace on copied state and prints the console
  log: every step every handset executed with the lab-time reading it ran at,
  every arrival at a named point and every resume from one with the arrivals
  behind it, the ledger rows with their flags, the pool's checkouts and
  returns, and anything still unfinished when nobody could take another turn.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace. `protocol.load_inventory`,
  `protocol.load_session` and `Session.report` are all public, so you can
  write a session of your own — your own benches, your own sizes, your own
  named points — and read the same console log back.
