From: Dagmar Holt (product) — Fwd: two tickets, reminders arriving at the wrong hour

I am forwarding two tickets. Both have come in since the clocks changed at the end of March, and support has had no answer for either of them.

Ticket 5120, a Berlin customer: their 09:00 standup has not moved in their own calendar, but our reminder for it now arrives at 10:00. One of their teams joined a client call after it had started.

Ticket 5133, a Sydney customer: the same complaint the other way round. Their 17:00 review reminder now arrives at 16:00, starting with the week after the 5th.

I do not know why this happens, and I cannot read `recur/schedule.py` well enough to guess. My one idea is that we are storing the wrong zone against the rule, and that once the right one is on it the times come out right again.

Can you take this on? `project_records/berlin-standup-march.json` replays the first customer's week, so you can see what they see. What I need is for those tickets to stop and to stay stopped through the next change of the clocks.

— Dagmar
