# Catalogue warehouse loader

`loader/` holds the nightly catalogue import. The scheduler starts it at 03:00
with the night's export, restarts it when a run reports itself `interrupted`,
and stops for the night when a run reports `completed`. Upstream publishes one
export a night under the same file name: on most nights the whole catalogue with
the day's new products in their place in it, and on a quiet night the same file
as the night before. In this feed, a row admitted on an earlier night is repeated
unchanged in later exports and is not removed; daily changes are new products and
their variants inserted into the complete export. The export is still the exact
catalogue for that night: the loader may not add rows of its own or change a
published value. `ImportConfig` carries the file name and a digest of the export
the run was handed.

- `loader/protocol.py` is the runtime contract. The warehouse side and the feed
  client are built against it and ship it with their release, so it is read-only
  here. It holds the `Storage` substrate and its `Transaction` (only committed
  transactions survive a restart), the position-addressed `SourceFeed`, the
  `ImportConfig` a run receives, the `admit` rule that decides whether a source
  row may join the rows admitted before it, `invariant_violations` for a whole
  database state, `STATUS_VALUES` with what each status means to the scheduler,
  and `require_report`, which states the fields every report must carry.
- `loader/importer.py` implements `run_import(storage, feed, config)`.
- `loader/support.py` is empty and available for helpers.

The upstream export is a retained stream, not an archive. After a run has read
to some position, the export only still holds the last `checkpoint_interval`
rows behind that point: `SourceFeed` refuses to re-read anything earlier and
`available_from` says where its window starts. `Storage.read_meta` and
`Storage.read_table` read committed state without opening a transaction; the
store they read is the same one every run of every night is handed, tables and
metadata alike.

Upstream combines the `rejected` lists from every report returned for one
night's export and opens one correction item per entry. Each source position
that the catalogue rules refuse must therefore occur exactly once across that
night's reports, with the reason those rules give it; a repeated entry creates
duplicate work just as a missing entry leaves a bad row unaccounted for.

The warehouse is live while we load it. The pricing feed and the merchandising
site read these tables continuously, including in the gap between two of our
commits, so whatever a transaction commits is on sale the moment it lands.

## What the warehouse team asks of the nightly load

The load runs in the window before the morning reports and shares the cluster
with them, so the warehouse team publishes an envelope for it and measures the
job against it after every release:

- at most `checkpoint_interval` rows changed in one transaction, because a
  transaction that writes more than that holds the write lock past the point
  where the morning reports start queueing behind it;
- at most `ceil(total_rows / checkpoint_interval) + 4` transactions in a run:
  one per batch of that size, plus four for the run's own bookkeeping and for
  the odd retry, since the cluster bills per transaction;
- the first commit within the first `checkpoint_interval` rows read, so that a
  run that dies has left something durable behind it rather than holding the
  whole export in memory;
- across all the runs a night needs to reach a `completed` report, no more rows
  written than the catalogue ends up holding plus one batch of
  `checkpoint_interval` rows for each run that stopped early, because the
  window is sized for one pass over the export and a restart that redoes work an
  earlier run already committed pays for that pass twice.

`run_project(action="status")` prints those numbers for the current export.

## Recorded nights

`project_records/` holds four nights this job has actually had: an interrupted
load, an export full of the junk rows upstream sends, a clean capacity load, and
a night with a mis-pointed export followed by the next scheduled run. Each file
names the attempts the scheduler made that night, what went wrong during each
one, and the note whoever picks that night up files with it: the scheduler's own
routing, the warehouse team's capacity review, or the thread upstream opens.

`run_project(action="replay", record="project_records/<name>.json")` runs one of
those nights against a copy of the workspace and reports, for each run: the
export it was handed and the position its window still started at, the report it
returned with everything in it or the error it raised instead, the transactions
it opened and the rows in the largest one, how far it read before its first
commit, the rows it wrote and the night's total beside the warehouse team's
allowances, the invariant failures in each of its committed snapshots, the keys
it left in the store's metadata, the rows in each table, and a digest of the
catalogue it left behind. A replay changes nothing in the working project and
delivers nothing to anyone.

`run_experiment` runs a Python script you write against a copy of the workspace,
so you can build exports of your own and drive `run_import` with them directly,
in whatever sequence you want to see.
