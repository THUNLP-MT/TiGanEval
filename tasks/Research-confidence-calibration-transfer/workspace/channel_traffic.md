# Marketplace traffic report — listings served at intake

Published monthly by marketplace analytics. Counts are of listings the router
served to intake, not of listings a reviewer saw.

## Marketplace listing queue

| channel | listings served, month just closed | listings served, same month last quarter |
| --- | ---: | ---: |
| web | 480 | 660 |
| mobile | 330 | 450 |
| partner_feed | 510 | 180 |
| reseller_import | 180 | 210 |
| **total** | **1500** | **1500** |

The month just closed runs to 2 September 2026. The comparison column is the
same calendar month one quarter earlier.

The reporting stack publishes the same table to a notebook as
`context["channel_traffic"]`, with `served_month_just_closed` and
`served_same_month_last_quarter` per channel. Each queue gets its own table.
