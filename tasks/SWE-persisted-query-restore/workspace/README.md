# Kerbside handset

`handset/` is the query cache the field app's screens are built from, plus its
side of the device store. One process holds it, and the operator's console moves
the clock, scripts what the depot answers, opens and closes app processes, and
enters screens.

- `handset/protocol.py` ships in the app release and is the same file in the
  crew tablet and the depot's web console, so it stays as it is. It owns
  `QueryState` and `derive_result`, the screen every list, banner, spinner and
  "last updated" line is built from; `status_for`, `apply_success` and
  `apply_failure`, the writes a finished load makes; `cache_key`, `slot_name`,
  `snapshot_payload`, `snapshot_key` and `snapshot_state`, the device format;
  `StoredCopy`; the `Clock`, the `DeviceStore`, the `QueryCache`, the `Depot`
  and the `EventLog`; and `settle_fetch` and `run_query`, the load driver.
- `handset/persister.py` is ours: `Persister` with `save`, `restore_one` and
  `restore_all`.
- `handset/adapters.py` is empty and ours too.

## How the app is wired

The app builds one `Persister(store, config)` per process. Two things then use
it, and which one runs depends on how the crew got to the screen.

- A screen's first load calls `run_query`, which asks `restore_one(query_key)`
  before it goes anywhere near the depot. That is the deep link: the crew taps
  a job in the shift list and lands on it.
- The process start-up calls `restore_all(cache, clock=clock, events=events)`
  once, before any screen is entered, so a cold open has its screens without
  signal. Start-up hands the rebuild the same clock and `EventLog` every load
  path in the app is handed. Nothing guarantees it has finished before the
  crew's own first pull-to-refresh lands; on a handset that finds signal in the
  middle of the yard it routinely has not.

Pull-to-refresh calls `run_query` with no persister, because the crew asked for
the depot and not for the device.

## Operations notes

- The background writer runs on a timer while the crew works. It saves whatever
  the query held at that instant by calling `Persister.save(query_key, state)`.
  The resulting slot must be usable by a later app process. Nothing tidies the
  state before that call, so a slot can hold a load that was in flight, or a
  status written a moment before the error beside it changed.
- `fetch_status` describes a load running in the process that wrote it. The
  screen puts a spinner up while it is anything but `idle`, and the crew cannot
  act on a screen that is still loading.
- `load_completed` in the `EventLog` is the counter the team watches to see how
  often a van actually reaches the depot; it is what the weekly signal-coverage
  figure is built from, and the depot plans the next day's rounds off that
  figure. The screens' own success hooks hang off the same completion path.
- Every stamp in a snapshot is a clock reading in milliseconds from the process
  that wrote it, and the crew's "last updated" line is `data_updated_at`.

## Recorded sessions

`project_records/` holds five sessions the team replays before a change to the
restore path goes out.

- `run_project(action="status")` lists the handset files and the five sessions
  with the queries each one has on the device.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  session against the current workspace on copied state and prints the console
  log: what was written onto the device, every operation the console drove, the
  screen each one left, anything the app raised there, how many loads completed
  and how many calls reached the depot at each step, the queries a rebuild found
  and left behind, and the depot's own log.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `Persister`, `QueryCache`
  and `run_query` through any sequence of your own.
