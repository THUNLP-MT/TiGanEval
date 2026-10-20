# Relay

`relay/` is the outbound HTTP client every collection job in the platform runs
its requests through. One process holds a job's run; the console moves the
clock and decides what each host answers.

- `relay/wire.py` ships in the platform release and is the same file in the
  other collectors, so it stays as it is. It owns `Address` and `parse_address`;
  `host_covered`, `path_covered` and `default_under`; `parse_stamp`; `Request`,
  `Reply`, `grant_lines`, `read_grant_header` and `format_grant_header`; the
  `Clock`; `JobProfile`; the `Host` models the jobs talk to; and the `Journey`
  that runs one job.
- `relay/vault.py` is ours: `GrantStore`.
- `relay/extras.py` is empty and ours too.

## How a run is wired

The platform builds one `GrantStore` per run, from the job's `JobProfile` and
the console's `Clock`, and every request of that run goes through it.
`Journey.go` calls `present(request)` for the name/value pairs to put in the
request's `Grant` header, sends them, and then calls `absorb(request, reply)`
with whatever came back.

A single sweep touches several hosts: the vendor's desk host, the subhost that
serves records, the asset origin and the mirror the vendor's edge serves, the
old plain-text listener that is still up, and the third-party analytics
endpoint marketing asked us to ping on every run.

## Grants on the wire

A host hands a grant over in a `Grant-Set` header, written as `name=value`
followed by `;`-separated attributes: `Scope`, `Under`, `Ttl`, `Until`, and the
flag `Sealed`. `Ttl` is a number of seconds. `Until` is a wire timestamp, which
carries a comma of its own after the weekday. Some hosts write one grant per
header; some write several into one header value, separated by commas.

The client presents what it is holding in a `Grant` header, as
`name=value` pairs separated by `; `.

## Operations notes

- `JobProfile.max_grants_per_scope` is the size the platform gives a job's store
  for any one scope. The tile hosts hand back a fresh grant with every reply,
  one per tile, and a host refuses a request whose grant header is larger than
  the size it publishes: `431 grant_header_too_large`.
- A host refuses a header that carries the same grant twice with
  `400 repeated_grant`, and answers `403 unexpected_grant` for a grant value it
  never issued itself. `401 stale_session` means the value was one of its own
  and is no longer live; `401 login_required` means the request reached a path
  that needs a session and carried none.
- A host that reads a session out of the header takes the first grant of its
  session name that it finds there, and writes the desk it acted for into its
  own audit line. Our request log prints that next to the desk the run had
  entered as, which is how the vendor's audit and ours are reconciled. Entering
  a desk is itself a request, and the desk it establishes exists only once the
  reply is back, so the line for that request names whatever the run arrived
  carrying; the reconciliation starts from the request after it.
- The vendor's sites are not the only ones a sweep reaches, and one of the
  competitors we crawl has a name that ends the same way theirs does.

## Recorded traffic

`project_records/` holds four stretches of relay traffic the team replays
before a change to the client goes out.

- `run_project(action="status")` lists the relay files, the job profile, and the
  four stretches with the hosts each one involves.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  stretch against the current workspace on copied state and prints the request
  log: every request in order with the clock reading, the grant header it
  carried, how many grants that was and how many bytes of header against the
  size that host publishes, the job profile the run was sized by, the
  status and reason the host answered with, the desk the host acted for next to
  the desk the run had entered as, and the raw `Grant-Set` values the reply
  handed back.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `GrantStore`, `Host` and
  `Journey` through any sequence of your own.
