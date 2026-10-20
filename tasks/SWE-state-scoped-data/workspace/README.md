# Order-fulfilment workflow engine

`fulfilment/` runs one order at a time through the chart in
`fulfilment/order_flow.py`. The floor tooling raises an event, the engine picks
the transition, and the order's handlers read and write the order's data as it
moves.

- `fulfilment/protocol.py` is the runtime contract. The floor tooling and the
  audit reader are built against it and ship it with their release, so it is
  read-only here. It holds `Chart` (the state tree, the fields each state
  declares with their types and defaults, the transitions, the resume points and
  how far each one reaches), the path helpers `scope_chain`, `exit_path`,
  `entry_path`, `descend`, `declaring_state` and `is_internal`, the
  `ChangeRecord` the audit reader consumes, and `ScopeError` with the three
  codes a refused handler step carries.
- `fulfilment/engine.py` is read-only for the same reason. `Engine` consumes the
  events the floor raises, picks the transition out of the chart, runs the
  handlers, calls the scope layer, and reports what each event did.
- `fulfilment/order_flow.py` is the chart this service runs. Read-only: the
  floor raises these event names and the audit reader is built against these
  state and field names.
- `fulfilment/scopes.py` holds `ScopeManager`, the only part of the runtime this
  project owns. `Engine` reaches it through `begin_event`, `enter`, `leave`,
  `read`, `write`, `values` and `changes`, and through nothing else.
- `fulfilment/helpers.py` is empty and available.

## How one event runs

`Engine.send` calls `begin_event`, then the transition's own handler step in the
innermost active state, then the exit handlers of the states the order is
leaving innermost first, then `leave`, then `enter`, then the entry handlers of
the states it is entering outermost first. An internal transition runs its step
and stops there.

A handler names a field, not a state: `Chart.declaring_state(state, field)` says
which state on the chain owns that name. `Chart.declared(state)` returns the
declaration itself, the one every order of this chart is started from.

Several orders run through one process at a time. The evening batch puts the
whole shift through a single engine process, one event at a time.

`order_flow.py` is not the only chart on this engine. The claims team run their
returns assessment on the same `Engine` and the same `ScopeManager`, with a
chart of their own, and the shift report both teams file comes out of the same
place.

## What reads this data

- The **floor tooling** reads `values()` between events to show a picker where
  an order stands. A picker sent back to a step is doing that step again, so the
  tally on the screen is this pass over it; a tally carried over from the last
  pass has had pickers re-scan shelves they had already cleared.
- The **audit reader** consumes `changes()` after every event and files what it
  gets as that event's account of the work. It reconciles the account against
  the order itself: what a step was holding when the event began, plus the
  event's lines for that step, has to come to what the step is holding when the
  event ends. A step the order walked into during the event opens at nothing,
  and a step it left closes at nothing, so the order taking a step up and the
  order giving one up are both movements the account has to carry. The shift is
  reconciled against those accounts, so a movement with no line against it is
  one nobody can account for, a line that turns up twice is counted twice, and a
  line that belongs to the step before is charged to the wrong step.
- **Held orders** come back through a resume point. `order_flow.py` declares
  where an order comes back in and how far below that state the point reaches.

## Recorded scenarios

`project_records/` holds four scenarios this service has actually run: the order
support escalated, an evening batch, an order held overnight, and a pick run
through the recount step the shelf team wrote.

`run_project(action="status")` prints the chart: every state, the fields it
declares with the value each one starts at, and the resume points.
`run_project(action="replay", record="project_records/<name>.json")` runs one
scenario against a copy of the workspace and reports what the engine said about
each event: the states the order is in, its data before and as each state was
entered, the audit lines, and any handler step the engine would not serve. A
replay changes nothing in the working project and delivers nothing to anyone.
`run_experiment` runs a Python script you write against a copy of the workspace,
so you can build a chart of your own and drive `Engine` with it directly.

Where the floor or the audit reader kept something of their own from before the
generic runner landed — the tooling screen for the morning an order came back
off a hold, the lines the reader filed for a handful of events — the replay
hands that back beside the run it just did, so the two can be set side by side.
