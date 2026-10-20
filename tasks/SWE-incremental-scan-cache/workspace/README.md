# CI security-scan workspace

`scanner/` holds the pipeline's static security scanner.

- `scanner/protocol.py` is the analyzer release's own contract: the check table,
  the `ScanOptions` configuration, the metered `run_checks` analysis step, the
  read-only `SourceTree`, the byte-accounted `CacheStore`, the `RunContext` a run
  receives, and `require_report`, which states the fields every scan report must
  contain. Every worker in the fleet runs this same file and it ships with the
  analyzer, so it is not ours to change.
- `scanner/engine.py` implements `scan(tree, store, options, context)`.
- `scanner/exchange.py` implements `export_cache(store, context)` and
  `import_cache(store, blob, context)`, used when a worker starts from another
  worker's cache instead of a cold scan.

`scanner/engine.py` and `scanner/exchange.py` are the pipeline's own code and are
the two files edited here.

`protocol.clean_scan(tree, options)` analyses every file with no cache at all; it
is what the pipeline runs when incremental mode is off, and it is what the
morning report is compared against when anyone doubts it.

## The volume's cache budget

The build volume gives the scan cache 5000 bytes for every file in the tree
being scanned. Each run is handed that number as
`RunContext.cache_size_limit_bytes`, together with `cache_expiry_days`, the age
from when a saved result was produced after which a result the current run does
not need counts as dead weight. Reading a saved result does not reset that age
or rewrite it. Storage states that age in days, the way the operators of the
volume talk about it, while the instant the pipeline hands a run arrives in
seconds; `protocol.SECONDS_PER_DAY` is where the two meet. The budget is sized
for the checkout in front of the pipeline, which is why saved results for files
that are no longer in the tree, and saved results past expiry that the run does
not need, are the nightly clear-out's job rather than an operator's. Whatever a
run leaves in the store is what the volume carries until the next run, and the
volume is shared with every other job on the box.

The volume meters writes as well: it allows a run in which nothing changed 256
bytes for every file in the tree plus 512 bytes of bookkeeping.

The nightly does not settle on one analysis configuration. Release nights run
the release profile and ordinary nights the default, the severity and
confidence floors move with whatever the security review is asking for that
week, and analyzer releases land under both. The pipeline goes back onto
settings it has already run as often as it moves onto new ones.

`run_project(action="status")` prints the published envelope for a rehearsal
tree, and every replayed run prints what that run left on the volume and what it
wrote next to the limits it was given.

## Fleet transfers

Workers do not all pick up an analyzer release on the same day, and an exported
bundle is a JSON object that declares its `format_version`. The warm-start step
calls `import_cache` inline in the scan job, before the run itself, so whatever
that call has to say about the bundle has to come back in the mapping it
returns: an exception there takes the whole job down and the worker produces no
report that night. The transfer step deduplicates bundles by content hash before
shipping them around the fleet, and it re-exports a worker's cache whenever it
ships. Checkouts also sit at different places on different workers —
`/srv/ci-1/checkout` on the old boxes, `/opt/agents/ci-2/src` on the new ones,
with the timestamps each box's own checkout wrote.

## Recorded rehearsals

`project_records/` holds four recorded stretches of this pipeline.
`run_project(action="replay", record=...)` runs one of them against a copy of
this workspace and returns what it measured: each run's analysed files, its
report and a full re-analysis of the same tree as separate count-and-fingerprint
summaries, its cache summary, and the cache left on the volume beside that run's
limits. Import events likewise show the receiving store's fingerprints before
and after the call separately. A replay does not compare these measurements,
change the working project, or deliver a checkpoint.

`run_experiment` runs a Python script you write against a throwaway copy of this
workspace, with `scanner` importable, which is the way to put a case the
rehearsals do not contain in front of the scanner.
