Can you make `pricing/recovery.py` read the two fields I put in the rulebook last June? I own the rule language here; the prototype sitting in that file is Dinh's and it has never looked at `on_error` or `retry_on_error` at all.

What put this on you: on 14 July `bundle_discount` reached for a third line on two orders that were filed with two, and both came out of the run at nothing while the ledger kept the charges the rule had already written against them. Finance held the whole invoice run and the desk repriced the pair by hand before nine. Replay `project_records/night-0714-invoices.json` and order 4912 is the one to sit with.

Every rule in `pricing/rulebook.json` already carries an `on_error` and a `retry_on_error`. What I want out of them: when a rule blows up on an order, price that order from its own `on_error` rather than from zero, and try the flagged ones again before falling back, so that one bad order costs us one order instead of a night.

— Rosa (INC-2214)
