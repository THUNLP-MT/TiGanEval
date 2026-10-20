# Record pipeline lineage audit

`lineage/` is the audit security runs over the record pipeline before a release
goes out. One run is handed the pipeline's modules by the release checkout and
returns one report; the release gate diffs that report and the triage console
renders it for the pipeline teams.

- `lineage/protocol.py` is the part the privacy office signed off and the triage
  console imports, so it stays as it is. It owns `PERSONAL_FIELDS`, `MASKS` and
  `EXPORT_SINKS` with the argument of each sink that actually leaves, `carries`
  for one expression, `ModuleSet` with the pipeline's modules and steps,
  `body_nodes` and `assignments` for reading one body, `Finding` with
  `finding_at`, `finding_key` and `require_report`, `baseline_findings` for the
  checks the audit already had, and `reference_flows`, which spells out what one
  module leaks when it is read on its own.
- `lineage/tracer.py` is ours: `scan(modules)` returns the report.
- `lineage/summaries.py` is ours: what the audit knows about the pipeline's own
  steps. Empty so far.

## How the pieces behave

The pipeline is a set of modules and a step is a module-level function; step
names are unique across the pipeline, so a call by name names one step. A
personal field enters a step where its source names one, travels into whatever
is built out of it, and is dropped only by one of the masking helpers. An export
leaks when the argument the sink sends carries a personal field.

The release checkout hands the audit the modules in the order it walked the
working tree, and the two build workers do not walk it in the same order. A
commit is audited on whichever worker is free.

## Operations notes

- The gate diffs the rows the office signed off last quarter against what a run
  returns, and fails the release when they do not match. Every team using the
  audit has already triaged and signed off on those rows.
- The triage console keys a reviewer's comment to the module, line, column and
  check id of the row it was left on, and counts open rows per team.
- The pipeline teams refactor continuously: the case-handling work was split
  across modules in week 12, and the intake steps the week before that.
- A run that reads more than `STEP_BUDGET` expression nodes without settling is
  given up on, so a pass that does not finish fails the gate rather than holding
  the release train.

## Drills

`project_records/` holds the four drills security replays before a checker
change goes out. Each one looks at a different part of the audit, so the replay
prints different columns for each.

- `run_project(action="status")` lists the lineage files, the field, mask and
  export tables, and the drills.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  drill against the current workspace on a throwaway copy and prints what this
  checker did at every scan of it.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can hand `scan` any pipeline of your
  own and compare it against `reference_flows`.
