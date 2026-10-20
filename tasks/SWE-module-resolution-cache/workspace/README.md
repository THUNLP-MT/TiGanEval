# The scripting runtime

`runtime/` is what every worker in the analytics fleet runs a job on. A job is a
small declaration file; the shared code a job leans on lives in kit files, and a
job or a kit reaches one with `use <name>`.

- `runtime/protocol.py` ships in the platform release and is the same file on
  every worker, so it stays as it is. It owns `FileStore` with `exists`, `stat`
  and `open`, and `FileIdentity`, which is how the store says which file
  something is; `Kit`, `Catalog`, `LicenceDesk`, `Runtime` and `LoadContext`;
  `activate`, which runs one file's declarations; `trace_line` and
  `read_trace_line`, the one line shape the fleet's log reader knows; the errors
  the loader raises, `MissingKit`, `ActivationError` and `CycleError` among
  them, with `read_cycle_chain`, which is how the fleet reads a `CycleError`'s
  chain back into the kits a loop went through; and `simulate`, which drives one
  recorded stretch.
- `runtime/loader.py` is ours: `Loader` with `reset`, `cache_info`,
  `cache_keys`, `resolve` and `load`.
- `runtime/support.py` is empty and ours too.

## The store

`store/` is a copy of the deployment's file tree, so `store/opt/kits/tax.kit` is
the file the store holds at `/opt/kits/tax.kit`. `/srv/kits` is a link entry
laid down over `/opt/kits`, which is where the platform team deploys the shared
kits; `/opt/kits-legacy` is the directory the shared kits used to live in and is
still on some workers' kit paths while the migration finishes. Jobs live under
`/srv/runs/`, and a job folder may hold kit files of its own.

`FileStore.stat` says which file a store path reaches; `FileStore.exists` says
whether anything is there; `FileStore.open` reads it. There is no call that
hands back a tidied-up path, so `stat` is the only thing that says whether two
paths are the same file.

## How a job runs

`simulate` drives one stretch: one `Loader` serves the whole stretch, `reset()`
is called before each run in it, and each job gets its own `Runtime` carrying
that worker's `settings`, the `invocation` the console started it with, the
run's `LicenceDesk` and `Catalog`, and its own `diagnostics` stream. A job's
body is run by `activate`, and every `use` inside it comes back through
`LoadContext.load` to `Loader.load`.

## Operations notes

`ops/nightly-runbook.md` is the on-call runbook for the nightly queue: what the
licence desk bills for, the two worker settings as they are typed today, how the
queue dispatches, where a job's log comes from, and the cron line the console
uses.

## Recorded stretches

`project_records/` holds four stretches the team replays before a change to the
loader goes out.

- `run_project(action="status")` lists the runtime files, the store tree and its
  link table, and the four stretches with the runs and jobs each one drives.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  stretch against the current workspace on copied state and prints what the
  console and the store recorded: every job with its declarations, its own log
  and how it ended; every `use` with the file it reached; everything the store
  was asked for and everything it opened; the licence checks; the catalog the
  run ended with; the loader's own report and the kits it says it is holding;
  and whatever the process wrote to its console.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can build a `FileStore` of your own
  and drive `Loader` and `simulate` through any sequence you like.
