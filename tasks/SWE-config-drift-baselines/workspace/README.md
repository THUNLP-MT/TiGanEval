# Estate configuration compliance

`estate/` is the service that tells the platform team how far each environment
has drifted from what it is declared to be. One process holds it. The console
drives it: it moves the clock to the night it is working on, hands the service
the scan the collector returned for one environment, and prints back whatever
the service is holding afterwards.

- `estate/protocol.py` ships in the platform release and is the same file in
  every region, so it stays as it is. It owns `CONFIG_KEYS` and
  `canonical_config`; the drift vocabulary with `drift_type_for`, `field_for`
  and `severity_for`; the four `Status` words; `compliance_score`;
  `record_key`; `render_value`; the `Baseline`, `Drift` and `Snapshot` shapes
  and the `drift_row`, `snapshot_row` and `baseline_row` the console prints
  them with; `NoActiveBaseline`; and the `Clock` the console moves.
- `estate/reconcile.py` is ours: `DriftEngine`.
- `estate/notes.py` is empty and ours too.

## What the console calls

```text
capture_baseline(environment, name, services) -> baseline id
activate_baseline(baseline_id)
delete_baseline(baseline_id)
scan(environment, services)                   -> Snapshot
acknowledge(drift_id) / ignore(drift_id)
drift_records()        -> every stored record, in any status
compliance_snapshots() -> every night's numbers
baseline_records()     -> every captured baseline
```

The console sets the clock before every operation, so `clock.now()` is the
night the operation belongs to. It reaches a stored record only through the id
the service gave it, and it finds that id again by what the row is about: the
environment, the service, the drift type and the field.

## Operations notes

- The record ledger is the durable audit history returned by `drift_records()`.
  The duty operator's morning queue is the ledger's `detected` rows: those are
  the newly found conditions that still need a decision. Acknowledge and ignore
  move a row out of that queue but keep the marked record in the ledger, even if
  its condition later clears. `resolved` is reserved for a still-detected
  condition that the service later sees clear. The release desk keeps a
  whole-service arrival or disappearance compact: the side on which the service
  exists carries the release reference named by the platform protocol, and the
  other side carries no value.
- The collector reads what the hosts answer. It reports a service's env
  entries, port bindings and mounts in whatever order the runtime holds them
  in, which changes whenever a host is recreated, and it leaves out a setting
  it has nothing to report for. A present baseline service with no confirmed
  deviation but at least one such omitted setting is counted in
  `unknown_services`, not `compliant_services`. A confirmed deviation takes
  precedence and puts that service in `drifted_services`.
- The compliance number is plotted per environment over a quarter and compared
  across environments in the Monday review, so two points on one line are only
  worth reading if they are shares of the same thing.
- The notification policy pages on the critical and high counts in a night's
  numbers. Those counters describe the conditions found against the active
  baseline on that night, whatever status their durable records hold. They are
  not counts of every row retained in the ledger or only of the `detected`
  morning queue.
- An environment can hold more than one captured baseline over its life -- an
  intake, a re-declaration after a release is accepted, an earlier one put back
  in force while a change board works through that release, an old one being
  tidied away -- and `protocol.NoActiveBaseline` is what the service raises when
  it is asked to compare an environment against nothing.

## Recorded runs

`project_records/` holds four recorded console runs the team replays before a
change to the compliance service goes out.

- `run_project(action="status")` lists the service's files and the four runs
  with the environments each one touches.
- `run_project(action="replay", record="project_records/<name>.json")` drives
  one run against the current workspace on copied state and prints the console
  listings: every operation and what it answered, each night's numbers next to
  the numbers the shell script the team ran before wrote for that same night,
  the rows written on that night, the complete record ledger it left behind,
  and the `detected` rows in the duty operator's queue.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `DriftEngine` through any
  sequence of nights, decisions and baseline events of your own.
