# Summary relay

`relay/` is the service between the desks that ask for a document summary and
the model backend that renders one. The front door accepts a call, the relay
decides what to do with it, and the front door holds that caller's connection
open until the relay answers it.

- `relay/protocol.py` is the runtime contract. The front door, the backend, the
  usage ledger and the replay substrate are built against it and ship it with
  the release, so it is read-only here. It holds the caller and ledger record
  shapes, the `RelayRuntime` the relay is handed, `reference_summary`, which is
  the backend's own renderer, and `simulate`, which replays a window.
- `relay/dispatcher.py` is the request path. `build_dispatcher(runtime)` is
  called once per process and the object it returns receives every callback.
- `relay/sharing.py` holds the in-flight table that was started during the
  invoice run and is not finished.

## The desks, the backend, the front door

The relay is shared by several customers. A principal belongs to a tenant and
carries a clearance. `run_project status` prints the directory: every desk, its
tenant, its clearance and the documents that desk has been given. Each customer
keeps its own half of that directory and its admins add and remove desks in it
as their staff change. `runtime.tenant_of`, `runtime.clearance_of` and
`runtime.is_authorized` are how the relay reads the directory while it is
handling a call.

A rendering does not arrive at once. The backend sends its pieces one at a time
through `on_chunk` and then either completes or fails, and nothing about that
timing is ours to choose. Neither is the order two callers land in: the front
door hands calls over in whatever order its sockets wake, and the same minute
replayed twice does not repeat the same order.

## Things that have happened to this service

- **Last month's close.** Finance invoiced the whole month out of the usage
  ledger. One customer's counsel disputed the bill and we spent three days
  answering it out of what the ledger holds, desk by desk, against the list
  their own admins keep of who asked us for what.
- **The capacity review.** Next quarter's backend fleet is being sized from
  `statistics()`. Those three counters are what the review reads off this side
  of the wire, and it checks them against the backend team's own request log.
- **March's re-pricing dispute.** These documents are edited through the
  working day and a desk quotes what it read straight back to a customer. We
  settled that dispute by showing, desk by desk, that each one had been quoted
  the document as it stood at the moment it asked.
- **Last spring's outage.** The backend shed load, this service retried the
  renderings that had died, and the second wave landed while the backend was
  still failing; the on-call spent the evening working out which side of the
  wire it was arriving from. The retry budget moved out to the desks' client
  library afterwards, and every call now arrives with that client's own
  `retry_budget` stamped on it.

## Recorded windows

`project_records/` holds four windows this relay has actually had. Each file
names the window and says what happened in it.

`run_project(action="replay", record="project_records/<name>.json")` replays one
of those windows against a copy of the workspace and reports what the relay did:
per window the callers accepted, the renderings the backend ran, how each caller
was answered, and the ledger entries written. A replay changes nothing in the
working project and answers nobody.

`run_experiment` runs a Python script you write against a copy of the workspace,
with `relay` importable, so you can build a directory and a window of your own
and drive `relay.protocol.simulate` with it directly.
