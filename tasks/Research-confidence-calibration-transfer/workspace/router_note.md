# Intake routing — integration note

Kept by partner integrations. It describes the paths, not any one quarter.

## Intake plans

Every listing that arrives is scored at intake and the intake log stamps it
with the routing plan in force when it arrived. Two plans appear in this
export: `route-2025-11` and `route-2026-04`.

`route-2026-04` went live on the marketplace queue on 27 June 2026. Nothing
before that date carries it and nothing after it carries the old plan.

## What changed at the cutover

The partner feed moved off the shared ingest path onto its own connector, and
the reseller import lost the shared ingest window it had been keeping with
the mobile path.

The web and mobile paths were unchanged, and the scorer artifact was not
touched at the cutover and has not been rebuilt since March.

## Channels

- `web` — the seller area a signed-in seller lists from.
- `mobile` — the seller app.
- `partner_feed` — the partner's own catalogue feed, taken on the connector.
- `reseller_import` — bulk imports from reseller tooling.

Volumes by channel are the marketplace traffic report's business, not this
note's; `channel_traffic.md` is the current one.
