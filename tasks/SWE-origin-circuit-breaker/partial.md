This is the follow-up off Thursday's checkout outage, and it is assigned to you. I am Yusra, the gateway's on-call, and I was on the bridge for it; the note below is mine, not the write-up's.

The payments provider started timing out at 14:02 and the gateway went on handing it work. The request pool filled with calls that were never going to finish, checkout was down for eleven minutes, and nobody worked out that the upstream was the cause until we were already deep into it. `project_records/checkout-outage.json` is that stretch of traffic; replay it against what is in the tree and you will see us still calling the host at the end of it.

I need the gateway to stop calling a host once it is clearly down. I think that is a counter and a timer: count the failures per host, and after five in a row send nothing there for thirty seconds. `gateway/breaker.py` already has the counter I started, which records failures and stops nothing. Take the wait from `cooldown_ms` on the client config rather than writing thirty seconds into the code, because the provider teams each ask for a different one.

Leave `gateway/protocol.py` where it is: it is the same file in the other three gateways and ships with them.
