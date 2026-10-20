# Provider ingest

`ingest/` reads the provider's nightly subscriber file and publishes it. The
scheduler fetches one drop a night at 02:30, hands it to `consumer.publish_drop`
and stops. The drop is a push: the provider deletes it once we have collected
it, so a payload we did not read tonight cannot be fetched again tomorrow.

- `ingest/protocol.py` is the runtime contract. The support console and the
  finance reconciliation job are built against it and ship it with their own
  release, so it is read-only here. It holds the column model (`Field`,
  `Record`, `Row`), the fallbacks a column may declare, the strict reading
  `structure` that the nightly pipeline has always used, and `describe_errors`,
  which renders a reading's problems into the lines support works from.
- `ingest/schema.py` is the provider's file as we have it under contract:
  `Subscriber` with a nested `PostalAddress`, a list of `OrderLine`, a
  `ledger_key` the ingest computes for itself, and our fallbacks for the columns
  that have one. It ships with `protocol.py`.
- `ingest/consumer.py` is the nightly publisher: it writes to the ledger, holds
  back what it cannot publish, opens the provider tickets, and applies support's
  later corrections. It also ships with `protocol.py`.
- `ingest/recover.py` is ours to finish.
- `ingest/support.py` is empty and available for helpers.

## How the file is read today

`structure(payload, SUBSCRIBER)` is all-or-nothing. It walks the payload,
collects every problem it finds with the path it happened at, and raises
`StructureErrors` without assembling anything. A caller that catches the error
gets the problems and no record. That is why one bad column has always cost us
the whole night's drop.

The contract lists the columns the provider sends, and the reading is closed
against anything else: a key we do not know about means the file changed. In
June the provider added a column without telling anyone and the nightly job read
past it for three weeks before finance noticed the drift, so an unrecognised key
now shows up in the reading's problems like any other.

A column's fallback in `schema.py` is a value we invented, not a value the
provider sent. `Ledger.write` records what we were told to treat as confirmed
alongside the row, and the finance team reconciles the provider's invoice
against exactly those columns.

## Recorded drops

`project_records/` holds four nights this job has actually had: the drop that
aborted, the drop finance queried afterwards, a night the order lines were
argued about, and one of support's correction rounds.

`run_project(action="replay", record="project_records/<name>.json")` runs one of
those nights against a copy of the workspace and reports what happened, payload
by payload: the keys the file carried, what was published, what the ledger row
holds, what the ticket says, and the lines the reading produced. A replay
changes nothing and publishes nothing.

`run_project(action="status")` lists the recorded drops and the columns the
contract declares. `run_experiment` runs a Python script you write against a
copy of the workspace, so you can build a payload of your own, push it through
`structure` and through `recover`, and compare them directly.
