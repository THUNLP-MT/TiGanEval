# quote-client releases

Maintained by the client library team. One entry per release, and the fleet
moves underneath it.

## 2.4.0 — 18 September 2026

- Telemetry moves to per-attempt receipts. Every call the client makes writes
  its own receipt carrying `attempt`, `outcome`, `retryable` and
  `client_version`. 2.3 wrote one receipt when the client was done with the
  operation and left `attempt` and `retryable` empty.
- In-process retry is unchanged in behaviour and now has an explicit deployment
  cap. This rollout tries a call the server marks retryable again, up to three
  attempts in total. Past that the client returns the last error to the caller.
- `retryable` carries what the server sent back. The client does not set it.

## 2.3.4 — 2 September 2026

- Connection pool sizing fix. No telemetry change.

## 2.3.1 — 11 August 2026

- First release with the shared deadline configuration.

## Fleet moves

| fleet | share of quote traffic | moved to 2.4.0 |
| --- | --- | --- |
| checkout-web | 30% | evening of 21 September, live from the 22nd |
| checkout-app | 25% | evening of 21 September, live from the 22nd |
| partner-api | 25% | evening of 22 September, live from the 23rd |
| internal-tools | 20% | evening of 22 September, live from the 23rd |

The edge pools run their own copy of the client and were moved to 2.4.0 on
14 September, a week ahead of the customer fleets and on the pool team's own
schedule. The pools run with in-process retry switched off, because a call that
has to be retried is the thing they are watching for.
