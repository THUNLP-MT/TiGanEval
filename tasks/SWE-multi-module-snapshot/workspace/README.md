# Plugin sandbox

`plugins/` is the sandbox the metering pipeline loads its transform plugins
into. One process holds it, and the operator's console loads the plugins,
queues the pipeline's work and drives it a step at a time.

- `plugins/protocol.py` ships in the pipeline release and is the same file in
  every ingest worker, so it stays as it is. It owns `Plugin` and `PluginHost`;
  `live_view` and `read_at` beside each other, `write_arena`, `step` and
  `balance`; the cell codec `cells`, `pack` and `book`; the delta codec
  `Delta`, `diff` and `apply_delta`; `digest`; the `Capture` a dump has to look
  like from the outside; and the errors the sandbox raises, `RestoreRefused`
  among them.
- `plugins/coordinator.py` is ours: `Coordinator` with `capture`,
  `capture_incremental` and `restore`, each taking the host and the plugins the
  console hands it.
- `plugins/support.py` is empty and ours too.

## How the sandbox runs

The host does the pipeline's queued work whenever an arena is touched and
whenever the console steps it. There are no threads and no wall clock, so a
recorded run comes out the same every time. `host.epoch()` says how much of
that queued work has been done and `host.pending()` how much of it is still
waiting.

Plugins keep their `key` across a reload; the loader's list order does not, so
`host.plugins()` puts a reloaded plugin back wherever there was room for it. A
key identifies the slot across reloads, but it does not turn another `Plugin`
object into the one the host loaded: membership is the exact object returned by
`host.plugins()`. A
plugin comes back from a reload with a fresh arena and, when the pipeline team
has changed its cell layout, with a different `layout` — bytes laid out for one
layout are a different set of numbers in another. The block the loader reserves
for it is whatever it has room for that day, so `capacity` moves across a reload
too. The console loads and unloads plugins while a batch is running, so the set
the sandbox holds at one moment is not the set it holds at the next.

## Operations notes

- The debug volume is 200 MB and a busy batch has us taking about twelve dumps
  a day. For a later dump in a chain, the console persists `delta(key)` to that
  volume; `image(key)` is the reconstructed view it prints and is not stored a
  second time.
- The roll-up plugin's first cell and the meter plugin's cells add up to what
  the loader declared for the batch, and the pipeline's work keeps them there: a
  hand-off subtracts from one and adds to the other in the same host write. That
  sum is how the on-call tells a real corruption from a bad reading. Only a
  reload moves it, because a plugin the loader re-instantiates comes back with a
  fresh arena. `book` reads the sum out of a pair of arenas and
  `PluginHost.balance` reads it off the live sandbox.
- Restore is the recovery path: it is run against a sandbox that is already
  wrong, by whoever is on call, from a dump that has been sitting in a ticket.
  A refusal is `RestoreRefused`; its `reason` code and `plugin` key tell the
  on-call which offered target blocked the recovery.

## Recorded runs

`project_records/` holds four runs of the sandbox that the team replays before a
change to the dump tool goes out.

- `run_project(action="status")` lists the sandbox files and the four runs with
  the plugins each one loads and the total the loader declared for it.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  of them against the current workspace on copied state and prints the console
  log: every step the console drove, the sandbox after each report step, what
  each dump held when the console read it — its recorded epoch, each plugin's
  length, fingerprint and cells, what it stores for each plugin, and the books
  as that dump has them next to the declared total — and, around a restore, the
  plugins the dump it was offered holds, every plugin's `write_seq` before and
  after, whatever the restore raised, and the arenas it left behind.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can load a `PluginHost` of your own
  and drive it through any sequence.
