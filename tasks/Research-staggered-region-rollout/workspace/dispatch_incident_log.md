# Dispatch on-call log — halcombe rollout

One line per page or change, in the order the on-call engineer wrote it.
`event` is the word the runbook asks for: paged, restarted, reloaded,
degraded, disabled.

| date | time | region | event | note |
| --- | --- | --- | --- | --- |
| 2026-02-07 | 22:05 | Millgate | paged | dispatch queue depth alarm, cleared on its own |
| 2026-03-10 | 23:50 | Riverbend | paged | assignment workers in a crash loop, restarted twice |
| 2026-03-11 | 02:15 | Riverbend | restarted | third restart of the assignment workers |
| 2026-03-11 | 09:40 | Riverbend | disabled | batching disabled |
| 2026-03-17 | 14:20 | Harrow Bay | reloaded | routing table reload after the depot move |
| 2026-04-03 | 06:40 | Cardean | degraded | label printer out at the north depot, 90 minutes |
| 2026-04-16 | 19:10 | Kingsmere | paged | courier sign-in errors, cleared by 20:00 |
