# Notebook console

`bundle/` is the part of the desktop console that puts a session in a file and
takes one back out. One process holds a console; the support desk drives it.

- `bundle/protocol.py` ships in the console release and is the same file in the
  desktop app, the headless runner and the exporter, so it stays as it is. It
  owns `Shell` with `run_cell`, the `events` hook points, the `OutputStore` and
  the `Out[n]` view over it; `split_outputs` and the four output kinds;
  `write_bundle`, `read_bundle` and the format constants; `schema_errors`,
  `BundleRejected` and `ReplayReport`; `format_error` and `now`.
- `bundle/recorder.py` is ours. The desktop app builds a
  `SessionRecorder(shell)` wherever an analyst can begin a recording — the
  toolbar and the session menu each build their own against the console in
  front of them — and calls `start(path, *, overwrite=False, redact=())`,
  `stop()` and `status()`, which answers
  `{"recording": bool, "path": str | None}`. `start` answers with the path it is
  recording to. A console can feed only one recorder at a time, whichever app
  entry point created it. A refused start raises before changing hooks, status,
  or a file; a normal return tells the app that recording began. Anything
  `start` raises, the app puts in front of the analyst.
- `bundle/replay.py` is ours too: `load_bundle(path)` gives back
  `(metadata, events)`, and
  `replay_bundle(shell, path, *, stop_on_error=True, store_history=True)` runs a
  file in the console it is handed.

## How the console runs a cell

`shell.run_cell(code, store_history=True)` fires `pre_run_cell` with what is
about to run and `post_run_cell` with what has just run, and both hooks fire for
every cell.

The front end does not number everything. The inspector panel and the chart
widgets re-evaluate cells with `store_history=False`; the console gives those no
number, so `execution_count` does not advance and the quiet cell shares its
place in the store with whichever cell is numbered next.

Everything a cell puts on screen goes into `shell.history`: `entries` per
execution counter, because `Out[n]` is served from there long after cell n
finished, and `printed` as one scrollback in order. `history.count` is how far
the scrollback has got and `history.since(mark)` is everything after a mark. A
recorder observes this history; starting or running one must not consume or
rewrite it, change a cell's result, or break a later `Out[n]` lookup.

## The bundle format

A bundle is a zip holding `metadata.json` and `events.jsonl`, one event per
cell. `schema_errors(metadata, events)` is the console's own description of the
format: it returns a code per fault and nothing at all for a file this console
will run. Customers run different console builds and send us files that have
been through mail, zip tools and text editors on the way.

The strings passed in `redact` apply to string content in recorded events. The
metadata is the bundle's structural header and is never redacted: its format,
platform, version, timestamps and counts must remain usable even when one of
those literal strings is also present in `redact`. Patterns belong to one
recording only; a later `start(..., redact=())` writes an ordinary, unfiltered
session.

## Files on this desk

- `samples/` holds two files a customer sent with a ticket.
- A recording names the path it writes to when it starts. The desk keeps what it
  writes under `exports/` and what customers send under `inbox/`, and the app
  makes either folder when a session first needs it, so neither is on this disk
  now.

## Recorded sessions

`project_records/` holds four sessions the desk replays before a change to
`bundle/` goes out.

- `run_project(action="status")` lists the package, the sample files and the
  four sessions.
- `run_project(action="replay", record="project_records/<name>.json")` drives one
  session against the current workspace on copied state and prints the console
  log: every operation in order, what each cell put on screen entry by entry,
  what the recorder reported afterwards and which hooks were attached, and, for
  every file the session read or wrote, its digest, its metadata and its events
  as they are on disk.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive a `Shell`, a recorder and a
  replay through any sequence of your own.
