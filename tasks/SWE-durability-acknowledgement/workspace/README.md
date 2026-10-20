# Storage engine — write path

`engine/` is the write path of the key-value store: the commit pipeline, the
write-ahead log, and the durability tracker the ack path and the replication
feed read from. One process holds a node; the pipeline drives everything.

- `engine/protocol.py` ships with the storage release and is shared with the
  replication feed, the recovery tool and the node console, so it stays as it
  is. It owns `Record`, `encode_batch`, `key_count`, `WriteAheadLog` with
  `append`, `sync`, `written_offset`, `synced_offset` and `fsync_log`,
  `recover(log)`, `durable_watermark(log)`, `Waiter`, `DurableState`,
  `DurabilityEvent`, and the `Engine` that runs a session and calls the
  tracker's hooks.
- `engine/durability.py` is ours: `DurabilityTracker`, with `set_listener`,
  `on_append`, `on_sync_complete`, `on_close`, `wait_for_durability`,
  `durable_state` and `durability_stats`.
- `engine/support.py` is empty and ours too.

## How the pieces behave

A commit is applied and framed into the log at append time. It is on the
device only once an fsync has covered its byte range; `recover(log)` returns
the records a restarted node finds, and `durable_watermark(log)` is the
highest sequence number among them.

The pipeline decides how many sync-requesting commits share one fsync. Under
load one fsync covers forty of them, on a quiet node each commit gets its own,
and the number changes with traffic while a node is running. A commit that
asked for nothing rides along inside somebody else's fsync, and a commit that
asked for one waits for whichever fsync reaches its bytes.

The tracker is given the record at `on_append` and the offset the device
reported at `on_sync_complete`. It never holds the log.

Once an fsync fails, the bytes it was covering are a hole. The device usually
comes back and later fsyncs succeed and report a larger offset, but recovery
still stops at the hole.

## Operations notes

- The read replicas ack from this engine too. They are configured without a
  durability listener; the listener is only wired on the primaries that feed
  the audit log.
- A deploy asks a node to close. Since the March freeze a node that still has
  a client parked on it when it closes is a blocked deploy — the last one was
  killed by hand at 03:14, and that is what took the replica set out.
- The replication feed reconciles the clients it released against the engine's
  own count, which the tracker reports as `durability_events` in
  `durability_stats()`. The two numbers are compared per node every morning,
  including on the replicas.

## Recorded sessions

`project_records/` holds four sessions the storage team replays before a write
path change ships.

- `run_project(action="status")` lists the engine files and the sessions.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  session against the current workspace and prints the node console's row for
  every step: the log's offsets, what recovery would return, the number this
  write path reports next to the same number computed from the log, the
  durability events delivered, every parked client and how it was settled, and
  the sequence numbers released so far.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can build your own session with
  `protocol.Engine(tracker, listener=..., sync_grouping=...).run(timeline)`
  and drive the tracker through any traffic, grouping or device behaviour.
