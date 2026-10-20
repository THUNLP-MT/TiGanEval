# Decision service

`policy/` is the rule engine behind `/v1/decide`. One gateway process loads a
bundle, answers requests against it, and reloads a new bundle when the bundle
owners publish one; several bundles come and go in a process each day.

- `policy/protocol.py` is shared with the API gateway, the operator console and
  the bundle owners' tooling, and ships in the gateway's release rather than
  ours, so it stays as it is. It owns the rule language and its `Policy`,
  `Definition`, `Test` and `Ref` nodes, `Evaluation` with the work meter, the
  per-decision cache and the record of what a decision evaluated, `Decision` and
  `RuleStat`, the naming helpers `rule_path`, `definition_id` and `package_of`,
  `success_rate`, `trace_ops`, and `reference_decide`, which spells out the
  semantics the hard way with no cache and no budget.
- `policy/engine.py` is ours: `Engine` with `decide`, `rule_value` and the
  definition walk.
- `policy/profile.py` is ours: the rule report, half written.

## How the pieces behave

Cost is counted in work units, never in wall-clock time. The platform moved off
nanoseconds two quarters ago: the same bundle timed on two gateway nodes gave
numbers a bundle owner could not compare, and a busy node made every rule look
slow. A decision that spends more than `DEFAULT_BUDGET` work units is given up
on and answered `indeterminate`, which is what the gateway returns to the
caller.

A rule is a set of definitions. Asking for a rule's value enters every one of
its definitions; a body holds when all of its conjuncts hold, left to right,
and is abandoned at the first one that does not. A rule's value is kept for the
life of the one decision that computed it, so a rule referenced from twenty
places inside one decision runs once and is read nineteen times.

## Operations notes

- The console keeps the loaded bundle's catalogue separate from the report for
  one decision. That report is built from the definition bodies recorded by
  the decision, and the console shows a success rate on each row. The shared
  rate helper returns 0 when the row it is given has no runs, rather than
  raising an error.
- The nightly job stores one report per shard, rolls a shard up per package for
  the bundle owners, and merges the shards into the per-bundle baseline it has
  been keeping since the vendor-access bundle landed. Last quarter's baseline is
  what this quarter's week-over-week numbers are read against.
- What the console and the nightly job call: `profile.stats(report)` for the
  rows, `profile.rate(row)` for the rate column, `profile.package_totals(report)`
  for the per-package view, and `profile.merge(left, right)` for the shards.
  Rows are `protocol.RuleStat`.

## Drills

`project_records/` holds the four drills the platform replays before an engine
change goes out. Each one looks at a different part of the service, so the
replay prints different columns for each.

- `run_project(action="status")` lists the policy files, the work-unit budget
  and the drills.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  drill against the current workspace on a throwaway copy and prints what this
  service did at every step of it.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `Engine` through any
  sequence of your own.
