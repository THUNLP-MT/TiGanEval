# Nightly archive

`nightly/` is the job the scheduler runs at 02:00 for every database we back
up. One process holds it; the operator's console supplies the night, the dump
and the destinations, and scripts what a destination does with what it is
handed.

- `nightly/protocol.py` ships in the platform release and is the same file on
  the two other backup hosts, so it stays as it is. It owns the archive
  object's layout (`write_header`, `parse_header`, `frame`, `SENTINEL`,
  `seal_trailer`), the reversible transform (`seal`, `open_sealed`,
  `chunk_nonce`, `stream_id`), the key helpers (`decode_key`, `key_id`,
  `KeyConfig`), the compressor every `.sql.gz` in the vault was made with
  (`compress`, `decompress`), the published read path `restore_stream`, the
  report row (`night_report`, `STATUSES`), and the console's model of a night
  (`DumpSource`, `Destination`, `NightRun`).
- `nightly/pipeline.py` is ours: `run_night(run)` runs one night and returns
  the row the scheduler files.
- `nightly/restore.py` is ours too: `open_archive(name, data, keyring)` is what
  the drill laptop calls on one object it pulled out of the vault.

## Where a night lands

Every night goes to two destinations: `nearline`, the filer in the same rack as
the database, and `offsite`, the vault the contract requires. A destination is
addressed by object name — `begin`, `write`, `finalize`, `close`, `delete` —
and an object appears in `listing()` from `begin` onwards, with `finalized`
false until something finalizes it. `read_object` is the destination's
published read-back path. Finalizing publishes an object to the retention
window, so both destinations' final stored bytes must be read back and verified
before either copy is finalized; a failed night must never become visible as a
published backup, even briefly.

`ARCHIVE_KEY` holds a key generation as 64 hex characters. The job
configuration can instead name a key file on the host;
`/etc/nightly/archive.key` is one that has been copied between hosts more than
once, and a key-file-only configuration is a normal supported configuration.
Nothing on the host
reads the ops key file — that lives with the drill kit — so the job has the
variable, whatever file the configuration names, and no way of telling which
generation is the current one.

## The quarterly drill

Rob picks a night off the offsite listing — any night still inside the window —
pulls the object down to a laptop that has `protocol.py` and the ops key file
on it, and runs the two steps in the runbook: first `restore_stream`, with the
key the object's header names, then `decompress`. What comes out has to load
into a scratch database. `nightly/restore.py` is the helper the laptop calls,
and the drill is the only thing in the estate that reads an archive object.
The window still holds nights the platform archiver sealed before the filer
went in as well as the `.sql.gz` this job has written since, and the sample
does not care which kind it lands on.

## Operations notes

- The retention window is 35 days. The sweeper deletes anything older, so a
  night that is not restorable is a night we no longer have.
- The missing-backup alert reads the offsite listing and pages when tonight's
  night has no object there. It matches on the night in the object's name, the
  name `object_name` builds, which is also how the retention sweeper and the
  drill sheet find a night. It cannot open an object, so an object of any size
  under that name is enough to keep it quiet.
- Key generations are rotated by notice. The ops key file lists every
  generation we have published, filed under the id `key_id` gives for it; a
  retired generation is destroyed 30 days after its notice, and the window is
  longer than that. Where a configuration names two places to look, nothing
  afterwards records which of them the job read.
- The vault's monthly session report lists every object we opened and did not
  close, and finance asks about each one.
- The nearline filer has had a bad month: on some nights it accepted every write,
  reported nothing wrong and stored a short object. The console can replay that
  and can replay the vault declining a write part way through.
- `orders` is the job the auditor sampled. A night's dump is around 34 KB of
  SQL and the `.sql.gz` objects in the vault run at about a third of that, which
  is what the retention budget was sized on.

## Recorded nights

`project_records/` holds four stretches the team replays before a change to the
job goes out.

- `run_project(action="status")` lists the job's files and the four records
  with the nights, destinations and drill each one involves.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  record against the current workspace on copied state and prints what
  happened: the row the job returned for each night, every event (including
  successful read-back) each
  destination saw, what each destination is holding afterwards with the bytes
  it stored and the object's leading bytes, and what the drill in that record
  got back for each object it opened.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `run_night`, `open_archive`
  and anything in `protocol.py` through any sequence of your own.
