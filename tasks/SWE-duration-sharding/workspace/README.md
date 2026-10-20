# CI shard planner

`sharding/` is the planner the CI runner loads on every machine of a run. One
run of the suite is `shard_count` machines started at the same moment from the
same commit. Each machine walks the working tree for itself, calls
`plan_shards` to find out which slice of the suite is its own, runs those
files, and calls `record_durations` when it is finished. The machines never
talk to each other, and no coordinator serializes their finish callbacks. The
only thing they share is `duration-history.json` in the working tree root.

- `sharding/protocol.py` ships in the CI runner's release rather than ours, and
  the build-cache key and the quarantine list are built against it too, so it
  stays as it is. It owns `Checkout` and `discover`, the `hash_shard` split CI
  has always used, `RunContext`, the `History` document with `parse_history`,
  `encode_history`, `read_history` and `atomic_write`, and `require_plan`.
- `sharding/planner.py` is ours: `plan_shards` and `record_durations`.
- `sharding/support.py` is empty and ours too.

## How the pieces behave

The runner starts every machine of a run with the same `RunContext`: the run
id, the attempt number, the generation the history file was at when the run
started, and the run's clock reading. A machine restarted after a failure is
given the run id and the generation of the run it belongs to, with an attempt
number one higher. Nothing in a run reads the machine's own clock, because a
replay of a run has to reproduce that run exactly.

`discover()` hands back the files in the order this machine's walk produced
them. The CI image and a developer laptop enumerate the same directory
differently, and so do two CI images with different layer caches, so the
machines of one run rarely see that order the same way.

The runner reads every plan through `require_plan` before it starts the
machine, and refuses to start a machine whose plan it cannot read. The plan is
also what the timing board reads: it is the only place the runner can compare
what a split was expected to cost with what it cost. The prices in it are
quotations from the history, not the planner's own weighting of a file:
`protocol.timings_as_of` is how the board reads what one generation of the
document holds for a file, and `ops/ci-budget.md` says what the cost report
does with the two numbers.

`duration-history.json` is the one file the machines of a run share. A
generation is one publication of the document; `RunContext.history_generation`
is the generation the run started at, and every entry carries the generation it
was published in.

`ops/ci-budget.md` holds the numbers the platform team is judged on and the
things CI keys off the shard index.

## Recorded runs

`project_records/` holds four runs of the suite that the platform team keeps
around, each with the scene it came from.

- `run_project(action="status")` lists the planner files and the recorded runs.
- `run_project(action="replay", record="project_records/<name>.json")` replays
  one of them against the current workspace on a throwaway tree and prints what
  every machine did: the discovery order it was handed, the generation it read,
  the files it planned, the plan the runner read back with the price it put on
  each file beside what that generation of the history holds for it, the history
  document after each write, each shard's predicted and realised minutes next to
  the same run under the `hash_shard` split, and, for the round as a whole, what
  that generation of the history prices the tree at per machine, the dearest
  price in it, and the budget line on those numbers.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can build a `Checkout` of your own
  and drive `plan_shards` and `record_durations` through any sequence.
