# Notification broker

`broker/` is the in-process broker the notification workers publish to and
consume from. One process holds it; the operator console drives the clock.

- `broker/protocol.py` is shared with the worker pool, the operator console and
  the queue dashboard, and ships in their release rather than ours, so it stays
  as it is. It owns `QueueSpec` and its properties, `Message`, the `Clock`,
  `BrokerState` with its queues, in-flight deliveries, settlement ledger and
  `snapshot()`, and the helpers that read and write a message's own history:
  `record_death`, `redeliveries`, `death_history`, `first_death` and
  `dead_letter_copy`.
- `broker/channel.py` is ours: `Channel` with `declare`, `publish`, `get`,
  `ack`, `reject`, `drain_expired` and `redelivery_count`.
- `broker/support.py` is empty and ours too.

## How the pieces behave

Deploys go out several times a day. A deploy stops the process and starts it
again; the drills call that step a restart.

The clock only moves when the operator moves it, so a drill can sit at one
reading for several operations, and a drill that never moves it stays at zero
throughout.

## Operations notes

- Last September's pager storm is why the busy queues carry a `max_length` at
  all. On-call spent that night reading alerts about a situation that had
  already moved on, and the caps went on the queues the following week.
- Support answers "what happened to my notification" from the settlement
  ledger. On-call triages a dead-letter queue in the morning from what the
  copies waiting in it carry.
- Queues belong to teams. `digest` and `receipts` are two different teams'
  queues and they share `holding`.
- Finance's nightly billing summary goes into `digest` alongside the digest
  team's own traffic. That queue keeps a notification for twenty seconds, which
  is sized for workers who clear it in a few of them; finance sets a longer life
  on the publish, because the summary is read by the morning shift hours after
  it goes in.

## Drills

`project_records/` holds the five drills the team replays before a broker
change goes out, each with the queues it declares and the notes on-call wrote
down the last time the drill was signed off. They are the situations the team
has bothered to record, not every situation the broker meets in a week.

- `run_project(action="status")` lists the broker files and the drills.
- `run_project(action="replay", record="project_records/<name>.json")` runs one
  drill against the current workspace on copied state and prints those notes
  next to every operation this broker performed: queue contents, deadlines,
  what each handout carried, and the settlement ledger.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can drive `Channel` through any
  sequence of your own.
