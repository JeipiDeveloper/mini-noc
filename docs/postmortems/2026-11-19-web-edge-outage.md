# Postmortem — Web edge outage (game day 01)

- **Date:** 2026-11-19
- **Severity:** SEV1
- **Duration:** 2 min 01 s of injected fault; 90 s to ticket
- **Service:** `web` (nginx edge)
- **Ticket:** `TKT-20261119-182220-B0BA`
- **Status:** Resolved
- **Nature:** Deliberate fault injection (game day), not a production incident

## Summary

The nginx edge was stopped for 120 seconds to validate the availability path end to end. `WebDown` fired after 75 seconds and a SEV1 ticket opened 15 seconds later. No other alert paged, because `ApiDegraded` was correctly inhibited by `WebDown`. The service recovered as soon as the container was started; no data was lost.

## Impact

- `app.local` returned connection failures for ~2 minutes.
- The demo page and `/api/*` were unreachable from the client's perspective.
- No data loss; Postgres remained healthy throughout.
- Error budget consumed: ~1.5 min of a 216 min monthly availability budget (~0.7%).

## Detection

| Signal | Value |
| --- | --- |
| Fault injected | 18:20:50 UTC |
| Alert active (`WebDown`) | 18:22:05 UTC |
| Ticket opened | 18:22:20 UTC |
| Time to detect | **75 s** |
| Time to ticket | **90 s** |

## Timeline

| Time (UTC) | Event |
| --- | --- |
| 18:20:50 | `docker compose stop web` — fault injected |
| 18:20:51 | Client requests begin failing |
| 18:21:05 | First failed probe scraped |
| 18:22:05 | `for: 1m` satisfied; alert becomes active |
| 18:22:20 | Alertmanager webhook delivered; bot opens SEV1 ticket |
| 18:22:51 | `docker compose start web` — recovery |
| 18:23:05 | Probe succeeds again; alert resolves |
| 18:24:20 | Resolved notification delivered (old 2 min `group_interval`) |

## Root cause

The edge container was intentionally stopped. There is no unexpected defect: the exercise validates that a hard dependency failure is detected, escalated and recorded.

## Contributing factors

- **Single edge instance.** By design, there is no second nginx; any stop is a full outage.
- **`for: 1m` plus a 15 s scrape interval** sets a floor of ~75 s for detection. This is a trade-off, not an accident.
- **The client had no alert of its own.** The outage was detected by the synthetic probe, not by the traffic generator.

## What went well

- The alert fired on the first evaluation after the `for` window, as configured.
- Inhibition prevented a second page for the API, which was a symptom.
- The ticket contained the runbook link and the correct severity without human intervention.
- Recovery was verified by the same probe that detected the failure.

## What did not go well

- The resolved notification took 2 minutes because `group_interval` was still 120 s. It was reduced to 30 s after this game day.
- The alert said "site down" but did not include a quick "last successful probe" timestamp; the on-call had to open Grafana to see it.

## Action items

| Action | Owner | Due | Status |
| --- | --- | --- | --- |
| Reduce `group_interval` from 2m to 30s | on-call | 2026-11-19 | done |
| Add `last successful probe` to the alert annotation | on-call | 2026-11-26 | open |
| Add a probe that represents the client path (DNS + HTTP in one check) | on-call | 2026-11-30 | open |
| Document the `for` window trade-off | on-call | 2026-11-19 | done (ADR 004) |

## Lessons

1. **Detection time is a product of configuration.** Shortening `for:` is the fastest lever, but it must be balanced against false positives on a noisy link.
2. **Inhibition is not cosmetic.** Without it, a single edge failure would produce two SEV1 pages and two tickets, splitting the response.
3. **A resolved notification is part of the incident.** If it lags, the on-call keeps working a ticket that is already over.
