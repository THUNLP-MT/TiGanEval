# The API service

`bootstrap/` is how this process comes up. One deploy console owns the run: it
moves the clock, registers the service manifest, and drives the deploy loop.

- `bootstrap/contract.py` ships in the platform release and is the same file in
  every service we run, so it stays as it is. It owns `Registration` and
  `Registry` (`register`, `names`, `declared_dependencies`, `instance`,
  `publish`, `resolve`); the boot `Ledger` with `acquire`, `release`,
  `open_handles` and `started_instance`; the `Clock`; the `Scheduler` that runs
  connect steps (`launch`, `advance`, `settle`, `drain`); `DeployConfig`; the
  errors a start-up raises; and `shutdown_all`, the process-exit helper the
  signal handler calls.
- `bootstrap/startup.py` is ours: `StartUp(registry, scheduler, ledger, config)`
  and its `bring_up()`.
- `bootstrap/planner.py` is empty and ours too.

## How the process boots

The console reads the service manifest, registers every service with the edges
that service declares, builds `StartUp(...)` once, and calls `bring_up()`. The
readiness script calls it a second time as soon as the first call returns,
because it has no way of knowing whether the first one was the deploy or a
retry. Once `bring_up()` returns, the console drains the deploy loop before the
process serves anything: a connect step that has been launched runs to its end
whether or not something waited for it.

Not every service has a connect step. Settings, feature flags and the objects
that only hold another service have none, and they are ready the moment they
are registered. The ones that do have a connect step take ticks to run it, and
some of them hand back a different object than the one that was registered.

While the boot runs, the platform's health endpoint keeps answering on the same
loop and resolves services out of the registry to do it. So do the request
handlers, from the moment the process starts serving.

## Operations notes

- `max_parallel_starts` is how many connect steps we let run at once. It is 4
  because the warehouse handshake service shuts the door on a fifth in-flight
  connection from one client, and the batch hosts share our client.
- `deploy_window_ticks` is what the deploy has before the traffic switch. It is
  300 for this service: the 08:00 cutover window is five minutes wide and the
  switch itself needs the rest of it.
- Handles are the things a host counts against us: a warehouse handshake, a
  write lease, a file lock. The platform reads `open_handles()` after every
  deploy. Anything still held there is held by a process that has already
  returned, so there is nothing left to kill and the next attempt runs into the
  host's limit.
- `shutdown_all` is the signal handler's helper. It is what runs when the box
  is going away.

## Recorded start-ups

`project_records/` holds four start-ups the team replays before a change to
`bootstrap/startup.py` goes out.

- `run_project(action="status")` lists the `bootstrap/` files and the four
  recorded start-ups with the services and deploy settings each one involves.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  of them against the current workspace and prints the boot ledger: every
  connect step with the tick it began and the tick it ended, what it handed
  back, every handle taken and given back, every resolve the health endpoint
  made and what it was given, what the console did with each operation, and the
  measurements from the run next to the settings they are read against.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can register a manifest of your own
  and drive `StartUp` through any sequence you like.
