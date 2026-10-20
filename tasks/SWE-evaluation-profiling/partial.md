Review comment on "Rule-level attribution for /v1/decide", draft 2 — Ines Okonkwo, platform

I am leaving this on Dana's draft rather than in chat, because you are the one picking the work up and section 3 is where I want you to start.

Since the vendor-access bundle went live, p99 on /v1/decide is roughly double what it was, and when the vendor team asks me which of their rules is doing it I have nothing to give them: the request log carries the decision and the total work units, and nothing per rule. That has been the whole of my answer for three weeks now.

Dana's plan is to time each rule and report the slow ones — a counter bumped in `policy/engine.py` where the engine looks a rule up, keyed by the rule's name, handed back with the decision. Half of that I believe. The counting I want. The naming I am not sure about, and the first cut in `policy/profile.py` is not something I would put in front of the bundle owners as it stands.

Can you take it from Dana's prototype to a report I can actually send them? Each rule's runs, and how many of those runs came back with a value. On for the nightly replay of `project_records/authz-latency-review.json`, off in live traffic.
