# Fleet job scheduler

`dispatch/` is the scheduler that hands the fleet's work to the workers. A
**job class** is a kind of work (`partner-settlement`, `ledger-export`); a
**job** is one unit of it. A worker reaches the scheduler over its own **link**
and **claims** the classes it can run. The supervisor builds one
`Assigner(state, clock, link)` per link and calls it from that link:

- `register_class(spec)` — the class this worker runs, as the build's start-up
  helper declares it;
- `claim(worker, job_class, rank=..., on_job=..., on_revoked=...)` — returns
  the claim id;
- `release(claim_id)` — the worker gives a claim up itself;
- `disconnect()` — the worker on this link has gone;
- `retire_class(job_class)` — the class leaves the fleet;
- `submit(job)` — the control plane puts one job into the fleet, over its own
  link;
- `finish(job_id)` — a worker reports that it is done with a job.

`dispatch/protocol.py` is the runtime contract. The operator console and the
worker agent are built against it and ship it in the same release, so it is
read-only here. It holds `Clock`, `JobClassSpec`, `Job`, `Claim` with the two
callbacks a worker registers, and `FleetState`, which every link in the
scheduler process shares and which the operator console reads through
`snapshot()`. `dispatch/assignment.py` is the scheduler itself.
`dispatch/support.py` is empty and yours.

## How this fleet runs

- **Replicas.** Every class runs on more than one worker now. Each replica is
  its own process on its own link, and they come and go all day.
- **The canary.** One pinned node runs each class alongside the ordinary
  replicas and claims at rank 10; the ordinary replicas claim at rank 0. The
  canary carries the build we are rolling out, so while it is up we want it
  doing the work, and when it goes away an ordinary replica has to carry on.
- **Rolling deploys.** We replace ordinary replicas one at a time, all of them
  at rank 0. Every time a class changes hands the partner sees the seam in its
  audit log, so a fortnightly deploy that moves work between equally ranked
  replicas ten times is ten seams.
- **Windows.** A settlement worker holds one open window with the partner for
  each job it has taken and the partner refuses a fourth window on the same
  account, so `partner-settlement` runs at `max_in_flight` 3 and
  `ledger-export`, which pins a warehouse cursor per job, runs at 2. The number
  comes from the fleet configuration that every build reads at start-up, so a
  worker on last month's build registers the same window as one on today's.
- **Offboarding.** When a partner leaves we retire its class. Every worker that
  was on that class holds an open connection on its side until something tells
  it otherwise, the ones that were standing by as much as the one that was
  running it.
- **Link drops.** A link drops when a worker's process exits or its network
  goes. `settle-old`, one of the replicas still on the March build, links behind
  the newer replicas and has never been the one running a class; it raises out
  of its shutdown hook every time the fleet takes a class off it, and that team
  is not changing it this quarter.
- **Restarts.** The supervisor rebuilds the fleet state and every link in place
  when the scheduler restarts. It does not restart the host process, and it
  runs about twice a week.

## Recorded shifts

`project_records/` holds four shifts this fleet has actually had.
`run_project(action="replay", record="project_records/<name>.json")` runs one of
them against the scheduler in the tree and reports what happened: every
operation the supervisor performed, which worker ran each job, the notices each
worker received, the most jobs each worker was holding at once next to the
window its class allows, and what the operator console showed at the end. A
replay changes nothing in the working project and delivers nothing to anyone.

`run_project(action="status")` prints the fleet's classes and their windows.
`run_experiment` runs a Python script you write against a copy of the workspace,
so you can build a fleet of your own — any number of links, any ranks, any
order of arrivals and departures — and drive it directly.
