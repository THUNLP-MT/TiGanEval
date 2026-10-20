# Ticket triage review

This is the support desk's workspace for the misroute review that goes to the
service board. `analysis.py` turns the desk's exports and the vendor's receipts
into the report the board reads.

## What is here

- `intake_last30.csv` is every ticket the desk received in the review window,
  as the intake export writes it: the day it arrived, the channel it came in
  on, its product line and segment, its priority, and the queue the shipped
  classifier routed it to. Some rows carry no segment.
- `label_pool.csv` is the March export the vendor labels from. The same
  columns, plus `model_margin`, which is how far the classifier's routing sat
  from its next choice.
- `adjudication_round.csv` is the sheet the two senior agents settled on 1
  September, one row per item they went through.
- `label_ledger.jsonl` is the vendor's receipt stream, one line for every row
  the vendor has delivered against this account, oldest first. The vendor
  writes it and the notebook cannot. It is the only record of what this
  account has been billed for.
- `labeling_contract.md` is what the vendor charges and how a session runs.
- `desk_notes.md` is the desk's own dated notes.
- `project_records/` holds the four working sessions this review has had, with
  the notes taken on the day.
- `protocol.py` is the shape the reporting stack calls the notebook through and
  reads its answer in. It ships with the stack, so it stays as it is.
- `analysis.py` and `support.py` are ours. `analysis.py` holds the report as it
  runs today: the share of the bought labels that disagree with the queue the
  classifier picked, the usual band around that share, a line for every receipt
  on the ledger, and an order placed on the items the model is least sure of.
  `support.py` has nothing in it yet.

## What the notebook has to do

`analyze(context, ledger)` returns the report and `next_collection(context,
ledger)` returns the labelling session to order next, or `"stop"`.
`protocol.py` documents both. The same file runs the reviews for the
field-service, harbour operations and ridge road desks, which sit on the same
vendor contract and arrive with their own exports, prices, balances and dates.

## Tools

- `run_project(action="status")` prints the desk, the vendor's terms and dates,
  the credits used and left, the sessions on the ledger and the records on
  file.
- `run_project(action="replay", record="project_records/<name>.json")` runs the
  notebook the way that working session ran it, on the ledger as it stood that
  day, and prints the notes taken then, the ledger behind them and whatever the
  notebook returned.
- `run_project(action="collect", session_id=..., items=[...])` places one
  labelling session with the vendor. It charges the set-up and the prices,
  waits for the delivery and appends the receipts to `label_ledger.jsonl`.
  Instead of `items` you may pass `draw={"rule": "uncertainty", "n": 20}`, with
  `rule` one of `uncertainty`, `confidence` or `pool_order` and optional
  `channel`, `segment`, `product_line` or `priority` filters. Sending the same
  `session_id` again returns the session already on the ledger and charges
  nothing.
- `run_experiment(script=...)` runs a Python program you write against a
  throwaway copy of this workspace. It does not reach the vendor, and nothing
  it writes is kept.
