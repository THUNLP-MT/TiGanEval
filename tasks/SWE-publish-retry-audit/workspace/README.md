# Release publishing

`publish/` is the step of the release job that puts the files a build produced
on the artifact host. One process holds it, and the release console moves the
clock, scripts what the host answers, and hands the publishing step the files
in whatever order the build finished them in.

- `publish/protocol.py` ships in the toolchain release and is the same module
  in the console and in the reconciliation tool we run with the vendor's
  support desk, so it stays as it is. It owns `Clock` and `StopSignal`;
  `Artifact`, `Body` and `open_body`; `PublishItem` and `plan_items`;
  `ReleaseConfig` and `load_release_config`; `Outcome`, `TRANSIENT_STATUSES`
  and `classify_outcome`; `parse_retry_after` and `http_date`; the `Host`; and
  `attempt`, `failure` and `report`, which are the shapes of the summary a
  release job prints.
- `publish/uploader.py` is ours: `Release`, with `publish`.
- `publish/support.py` is empty and ours too.
- `release.toml` is the release manager's. The console reads it and hands the
  publishing step a `ReleaseConfig`.

## How a release is published

The console builds one `Release` per run and calls `publish` once with every
`PublishItem` the release has: the build outputs and the extra files the
release carries, each already resolved to the place it belongs. The order they
arrive in is not the same twice, because it is the order that run's build
finished them in; `status` and a replay both print it as
`order_the_console_hands_them_over`. Two publishers are configured today, the
upload host and the mirror. Opening a mirror bucket is a connection, not a
publication: it moves no file and leaves nothing behind, and the host's log
calls it an `open` rather than a `put`.

A `Body` is drawn from an artifact and the host drains what it is handed.

## Operations notes

- The upload host answers every call with a status. `TRANSIENT_STATUSES` is
  what the vendor's runbook lists as the host's own weather. Anything else the
  host chooses is the host answering about this publish: 403 with "the
  publishing token was revoked" is as true the fourth time as the first, and
  the words the host used are what the on-call engineer needs in the failures
  list, not ours.
- The mirror has no statuses. Its errors say for themselves whether the
  trouble was passing, which is what `timeout` and `temporary` on the error
  are for.
- `delay_ms` and `max_delay_ms` in `release.toml` are the ordinary pause between
  tries and the hard ceiling the build window puts on any one pause. The
  ceiling still owns the clock when a host names a later instant.
- The vendor's rate limiter is why `Retry-After` is on some answers. A replay
  prints calls that arrived before the named instant per host as
  `calls_that_arrived_early`; the number is also how the team can see when the
  release window, rather than the host, bounded a pause.
- The console presses `StopSignal` when the release manager cancels or the
  build window closes. Nothing may go to the host after that. The release lab
  starts each rehearsal with an equivalent empty host and compares the prefix
  left by the same version at the same elapsed-time stop, including runs whose
  build-finish order differs.
- The release notes tool diffs the attempts block of a release against the
  previous release's, line for line, and that diff is what the release manager
  reads before signing a release off. A line that has moved reads there as a
  change.

## Recorded releases

`project_records/` holds four releases the team replays before a change to the
publishing step goes out.

- `run_project(action="status")` lists the publishing files and the four
  releases with the artifacts, publishers and settings each one involves.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  release against the current workspace on copied state and prints what
  happened: every call the host received with its clock readings, bytes and
  answer; what each target ended up holding next to what the build made; the
  summary the publishing step printed; and the pauses between tries next to
  the pause and the cap in `release.toml`.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `Release`, `Host` and
  `Clock` through any sequence of your own.
