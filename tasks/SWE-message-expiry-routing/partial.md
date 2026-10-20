NOTIF-412 — worker pool stalled all night on one notification

Ravi (on-call, notifications), assigned to you · opened 06:40

At 01:40 the pager went off for the whole pool: every worker busy, nothing moving. One malformed notification from the billing feed was the cause. The workers reject it, the broker puts it straight back at the head of `work`, and the next worker picks up the same one. That went round until 06:10, when I paused the feed by hand. About four hours of customer notifications queued behind it went out late.

Two other things came out of the night. While the downstream service was slow the feed queue climbed past anything we could drain, and one customer got an alert at 05:00 about a condition that had cleared at 23:00.

I need you to give me a night where nobody gets paged for this. My plan is three changes in `broker/channel.py`, which the README says is ours:

- after three failed attempts, put the notification in that queue's dead-letter queue instead of back in `work`;
- I read `message_ttl` as the queue's maximum lifetime, so do not hand anything out once it reaches that age;
- stop a queue growing past its `max_length`.

The queues already declare `dead_letter_queue`, `message_ttl` and `max_length` in their properties, and the code in the tree behaves as if they were not there. When you think it is done, replay `project_records/poison-message-drill.json` and show me it ending with `work` empty.

— Ravi
