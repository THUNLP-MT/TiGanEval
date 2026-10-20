# Edge gateway

`gateway/` is the outbound call path every service in the fleet uses to reach an
upstream. One process holds it, and the operator's console moves the clock and
scripts what the upstream fleet answers.

- `gateway/protocol.py` ships in the platform release and is the same file in
  the other three gateways, so it stays as it is. It owns `Url`, `Request`,
  `Response` and `ClientConfig`; `join_base`, `effective_url` and
  `resolve_origin`; `FAILURE_STATUSES` and `classify_outcome`; `RETRY_STATUSES`
  and `should_retry`; `apply_transform` and `deliver`; the errors the call path
  raises, `GatewayBlocked` among them, which is what a caller is handed when the
  gateway declines to make its call; the `Clock`, the `Transport`, and the
  `Session` that runs calls.
- `gateway/breaker.py` is ours: `Gateway` with `create` and `call`.
- `gateway/support.py` is empty and ours too.

## How the fleet is wired

The platform builds one base client at start-up and every service client comes
from it: `core.create(base_url="https://payments.internal", name="payments")`.
Twelve service clients are built that way today, and three of them point at the
same warehouse host — one at its admin port. Callers pass whatever they happen
to hold: an absolute URL, a path under their client's `base_url`, a `Url` the
router already parsed, or a `Request` another layer built.

A call is a generator, so several can be in flight in one process.
`Session.start` makes the call without running it, `Call.step` advances it to
its next transport boundary, and nothing reaches an upstream until a step
performs it. That is how the report workers behave in production: six of them
wake on the same timer and call the same upstream.

## Operations notes

- `cooldown_ms` is how long we leave an unwell origin alone. Thirty seconds is
  what the payments provider's runbook asks a client to wait, and the wait is
  measured from the moment the origin last failed us.
- `half_open_max` is how many calls we let through while we are finding out
  whether an origin came back. Waiting calls use the configured places while
  any are free; only calls beyond that number are refused. It is 1 everywhere
  except the search fleet. The 11 September incident was one upstream coming
  back and the whole report fleet arriving at once and knocking it over again.
- `FAILURE_STATUSES` is what the platform reads as "the origin itself is
  unwell". A status outside that list is the origin answering correctly about
  something a caller asked for: a 404 for a charge that does not exist tells us
  nothing about the origin's health.
- The platform's own health probe and the internal bookkeeping calls set
  `guarded=False`. They have to keep working while an upstream is out, because
  the health probe is how we find out that it came back.

## Recorded traffic

`project_records/` holds five stretches of gateway traffic the team replays
before a change to the call path goes out.

- `run_project(action="status")` lists the gateway files and the five stretches
  with the clients and origins each one involves.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  stretch against the current workspace on copied state and prints the access
  log: every operation and what the call it drove ended as, every attempt that
  left the process with its URL and clock readings, and what each origin
  received — including, for an origin the gateway refused, which clients it
  refused there, when it last answered, and how long it then waited before a
  guarded call reached it, next to the shortest `cooldown_ms` those clients are
  configured with.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `Gateway` and `Session`
  through any sequence of your own.
