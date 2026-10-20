# Rating run

`pricing/` is the nightly rating run. It reads the rulebook, prices every order
with the rule that order's product class names, and writes what it decides to
the billing ledger that finance reconciles the month against.

- `pricing/protocol.py` and `pricing/grammar.py` ship with the rating release
  and the invoicing service imports the same two files, so they stay as they
  are. Between them they own the rule grammar and `Node`; `Rule`, `Rulebook`
  and `load_rulebook`; `Env` with the append-only `effect_log`, `mark()`,
  `discard_after()`, the rating reservations and `fault_log`; `RunContext` with
  `attempts`, `attempts_left()` and `commit()`; the faults a rule body can
  raise, gathered in `EVALUATION_FAULTS`, with `ERROR_KINDS` and `OTHER_LABEL`;
  `AttemptsExhausted`, `StepBudgetExceeded` and `RunHalted`; `eval_node`; and
  `run_night`.
- `pricing/recovery.py` is ours: `run_region`, which the engine calls for every
  `rescue` node.
- `pricing/triage.py` is ours too: `label_for`, the label an incident is filed
  under.
- `pricing/rulebook.json` is the live rulebook. It is under change control with
  finance, so it is read here rather than edited.

## How a rule is priced

Each rule in the rulebook has a `body` and may carry `on_error`,
`retry_on_error`, `guard` and `cleanup`; a rule's `guard` names the triage
label its `on_error` branch is written for. The engine compiles all of that into
one recovery region around the body and hands the region to `run_region`; the
`rescue` form inside a rule's own source compiles to the same thing, so a rule
can carry a region inside its `on_error` branch. A body may commit to the
ledger with `charge()` and `audit()`, and may take a rating reservation with
`hold()` part way through.

`run_night` prices one night: `orders` (each with `id`, `rule` and whatever the
rules read), `vendor` (what `quote()` answers, in order), and `halt`, which is
the desk pulling the halt switch while one named order is being priced.

## Operations notes

- `max_attempts` in the rulebook is what one order may cost us in evaluated
  attempts. The vendor bills per attempt and finance asked for the cap after
  July's invoice; the engine counts an attempt every time a rule body is
  entered for that order, so `RunContext.attempts` is the number the invoice
  will agree with.
- `step_budget` is per order. It exists because September's lane comprehension
  in `tier_pricing` held the run open until 09:40.
- `max_open_leases` is per order. The vendor charges by the hour for every
  reservation still held, from the moment it is opened until it is given back,
  and refuses a second concurrent one for the same order at renewal.
- The desk's halt switch is how a bad night is stopped once it is running. It
  is the only way anyone has to stop the run before 06:00.
- The close report finance publishes at month end: 214 orders went through the
  rules that carry a closing branch in August and the report carries a close
  against every one of them. 209 came out with a price; of the five that did
  not, three are orders the close itself refused and two are orders whose
  trouble the rule had no branch for. Finance reconciles the month against that
  report and reopens by hand any order it has no close against.
- Last month's triage board, as operations published it: `lookup` 41,
  `conversion` 12, `declared` 6, `exhausted` 3, `other` 0. The two orders they
  rolled into the `lookup` row from the 22 July run were 5062 and 5077. The
  `exhausted` row is orders the run had to evaluate again with nothing left in
  their attempt budget; operations takes those three to the rating vendor
  rather than to us, which is why they are counted apart from the rest.

## Recorded nights

`project_records/` holds four nights the team replays before a change to the
run goes out.

- `run_project(action="status")` lists the pricing files, the rulebook limits
  and the four nights with the orders and rules each one covers.
- `run_project(action="replay", record="project_records/<name>.json")` prices
  one night against the current workspace on copied state and prints the
  telemetry: what each order ended as, with the price, the attempts it used
  next to `max_attempts` and the steps it used next to `step_budget`; every row
  the ledger holds, tagged with the branch and the attempt that wrote it; every
  incident raised, with the class and the label it was filed under; and the
  rating reservations opened, given back, still held at the end, and the most
  held at once for one order next to `max_open_leases`.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of the workspace, so you can build a night of your own and
  price it through `run_night`.
