# Ingest reliability review, 24 July 2026

Present: Kofi Mensah (platform, on call), Priya Raman (growth analytics).
Raised by: the ingest pager, 14 July 21:38.

## What happened

The catalogue team ran a full reindex from Tuesday 14 July to Thursday 16 July.
The reindex republishes an item event for every catalogue row it touches, and it
publishes onto `orders.reorder-confirmed`, the same topic the reorder
confirmations go to. It put roughly 50,000 extra events a day onto that topic
for three days.

`orders.reorder-confirmed` is provisioned at 42,000 events a day. When a day goes
over that number the collector sheds from the head of the buffer and does not
read the payload of what it sheds. The daily `accepted` and `dropped` counters
are in `ingestion_receipts.json` together with the topic's `ceiling_events`.

`experiments.assignment`, which the enrolment snapshot is written from, is a
separate topic with its own provisioning.

## Actions

- Catalogue to move the reindex onto its own topic. Owner: catalogue. Due 21
  August.
- Platform to raise the reorder topic to 60,000 events a day at the next
  provisioning window. Owner: Kofi. Due 4 September.
- Until then the topic carries what it carries; the watch has run at 45 percent
  since 27 July with nothing dropped.
