# Delivery portal request surface

`surface/` is what every partner call arrives at. One process holds it; the
console assembles a surface, sends requests at it, and reads what came back.

- `surface/protocol.py` ships in the partner platform release and is the same
  file in the billing, catalogue and identity services, so it stays as it is.
  It owns `Request`, `Response` and `Endpoint`; `seal` and `body_free_view`;
  `METHOD_ORDER`, `order_methods` and `allow_header`; `UNSET` and
  `layer_value`; `matches_path`, `path_values`, `guard_answer` and
  `run_operation`; `build_catalogue`, `published_operations` and
  `describe_path`; `usage_row`; and `METER`, the work meter.
- `surface/routing.py` is ours: `Router`, `Service`, and dispatch.
- `surface/metering.py` is empty and ours too.

## How a surface is assembled

A router holds operations. A service mounts routers under a prefix, and the
same router can be mounted more than once — the stream router is mounted once
per tenant, and the digest router is mounted at `/public` and at `/ops`. An
operation's mounted path is the prefix it was mounted under plus the path its
own router declares it at; that mounted path is what a partner calls and what
the published catalogue is keyed by.

Any name passed to `add_route`, `include`, `Router()` or `Service()` beyond the
operation's own fields is a setting for that layer, and `layer_value` is how
the platform reads one back. `in_catalogue` is the setting the portal has
today: it decides whether an operation appears in the document the partner
platform generates its client libraries from.

## Operations notes

- The delivery mirror sends a size probe before every pull, sizes the transfer
  from `content-length` on what comes back, and takes the status of that probe
  as the status of the pull it is about to make. Partners have opened tickets
  for bundles that arrived truncated and for bundles their token never covered.
- The digest rebuild costs what a rebuild costs. Operations run it on a
  schedule and have asked, more than once, that nothing else set it off.
- The older partner clients read a method list as permission to send everything
  in it. The mirror reads the same list the other way round: it will not ask a
  path how big something is unless the list says the path takes that question.
  The partner platform compares what a path advertises against the published
  catalogue when it regenerates a client, and Acme's last two client releases
  slipped on that comparison.
- Where one of these answers matters enough, a team writes it out themselves:
  `size_stream` reads the tenant index and costs one work unit where the feed
  page it is about costs forty-six, and `order_terms` carries the partner desk
  address, which is the only place a partner ever sees it.
- The monthly capacity report is `Service.usage_report()`, shaped by
  `usage_row`. Every operation that runs writes its own line to `METER` under
  its own name and the cost column is the sum of those lines, `size_stream`'s
  one unit among them. Finance opened the two hit columns the quarter the
  portal started answering partners about its own paths, because those answers
  reached no line in the cost column and the invoices came up short. The hourly
  job reads the report, folds its own estimates into the mapping it is holding,
  and writes the CSV; last quarter it folded them into the portal's live
  counters instead and the month's traffic went out twice. Finance bills a
  partner for the mount they call, so `/tenant/northwind/stream` and
  `/tenant/pinehurst/stream` are two invoices.

## Recorded traffic

`project_records/` holds five stretches of partner traffic the team replays
before a change to the request surface goes out. They are the stretches we kept,
not everything the portal serves: routers get mounted again under a new prefix,
partners are added between one release and the next, and a page that moves into
a new router leaves whatever used to read it mounted where it was.

- `run_project(action="status")` lists the portal files and the five stretches
  with the surface each one assembles, layer settings and all.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  stretch against the current workspace on copied state and prints the request
  log: the operations the assembled surface serves, what the portal publishes
  about them, what every request got back with its headers and work units, and
  the capacity report.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can assemble any surface of your own
  and send anything you like at it.
