# Rack diary, soak bay 2

One line per thing done to a rack. Kept by the bay, not by reliability.

| date | rack | entry |
| --- | --- | --- |
| 2026-01-05 | R-A | Loaded. L-11 six modules at 1.4 A, L-17 five at 1.4 A, L-22 three at 1.7 A. Case controller set to the plan's hold. |
| 2026-01-09 | R-A | Door seal replaced, no modules off the rack. |
| 2026-01-14 | R-B | Logger back from the workshop. It had been running on the slow profile since the bay was rebuilt last spring and is back on the fast profile the bay was set up for. Sample counter zeroed. |
| 2026-01-19 | R-B | Loaded. The whole of L-14: six modules at 1.4 A and four at 1.7 A. R-A was full, so L-14 went here. |
| 2026-02-03 | R-A | Case controller recalibrated against the bay's own thermocouple. Held. |
| 2026-02-24 | R-B | Fan bearing replaced. Rack down four hours, modules stayed in the case. |
| 2026-03-16 | R-A | Campaign closed on R-A. Last session read. |
| 2026-03-24 | R-B | Campaign closed on R-B. Last session read. |

## Loggers

Each rack has its own logger. It writes one sample per module per step of its
profile and hands the sample counter to the export, which is where
`sample_index` and `elapsed_h` come from. `logged_at` is the rack clock's own
stamp on the reading session.

R-A's logger has not been touched since the bay was commissioned. R-B's is the
one that came back on 14 January.
