Support escalated order 4471 to me this morning. It has sat since Tuesday and the picker had already given up on it, because the count the tooling put in front of her was not the count she had made. Replay `project_records/stuck-order-escalation.json` and the shape of it is there — `attempts` on `Fulfilling` climbs to 6 over a scenario the picker retried twice. Every shelf scan is moving the order's own counter.

Bram wants every state in `fulfilment/scopes.py` to keep its own data bag: the defaults it declares, filled when an order walks in, dropped when it walks out, the counters kept on the bag. I had taken that to mean a step only sees the bag for the state it is standing in; otherwise I cannot see how the shelf count stays out of the order count. I think he has the right file. I am not convinced the bag is the whole of what this layer owes the rest of the service, and I would rather you worked that out from the project itself than took his word for it, or mine. Anything you write has to sit there or in `fulfilment/helpers.py`, which is empty; the floor tooling installs `protocol.py`, `engine.py` and `order_flow.py` from its own release and puts its own copy back over ours on every upgrade.

I need you to send 4471 back to me with an attempt count the floor would recognise.

Ilse
