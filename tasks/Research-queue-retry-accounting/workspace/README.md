# Quote route failure review

This is the platform workspace for the September failure review on `/v1/quote`.
The capacity review asks one thing of it: what last week actually cost
customers.

## What is here

- `service_context.json` is the review as the platform export publishes it: the
  window and the evening block it covers, the route, the archive terms, the
  edge pools and how many probes each sends, the client fleets and their share
  of the traffic, and the daily dashboard.
- `request_rollup.json` is the receipt rollup, one row per minute, client
  version, attempt, outcome and retryable flag, with the number of receipts.
  It is about a megabyte, so read it from a script rather than by eye.
- `edge_pool_counters.json` is what the pool collector writes, one row per
  minute per pool: requests handled, probes emitted, probes spilled and the
  sink backlog reading.
- `client-releases.md` is the client library changelog and the fleet move
  dates, as the client team publish them.
- `capacity-review.md` is what went to the capacity review on Thursday, with
  what finance said and what the platform grants this review.
- `project_records/` holds the four working sessions this review has had, each
  with the operator's notes, the export as it stood that day, and the trace
  units that session had paid for.
- `trace_receipts.json` is the trace receipt ledger. The edge trace service
  writes it; the notebook cannot. It is the only record of what this review has
  been billed for.
- `protocol.py` is the shape the review stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the reading as
  it runs today: error receipts over receipts for the window, and a next pull
  aimed at the two evenings the dashboard puts highest. `support.py` is empty.

## What the notebook has to do

`analyze(context, receipts)` returns the report, and
`next_trace(context, receipts)` returns the next pool-minute to pull from the
edge archive or `"stop"`. `protocol.py` documents both. The same file runs the
reviews that follow this one.

## Tools

- `run_project(action="status")` prints the review, the archive terms, the
  pools, the fleets, the dashboard, how many trace units are spent and left,
  every unit on the receipt ledger and the sessions on record.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that session's operator ran it: on the export as it stood
  that day and the units paid for by then, and prints the session's notes, its
  dashboard, the last evening minute by minute and whatever the notebook
  returned.
- `run_project(action="collect", minute=..., pool=..., trace_id=...)` pulls one
  pool-minute out of the edge archive. It returns that pool's rows for that
  minute grouped by source and outcome, appends the receipt to
  `trace_receipts.json` and spends a unit. Sending the same `trace_id` again
  returns the same receipt without spending anything. A minute the archive no
  longer holds cannot be pulled at any price.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the trace service, and
  nothing it writes is kept.
