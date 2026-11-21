# Postmortem — Internal DNS failure (game day 02)

- **Date:** 2026-11-19
- **Severity:** SEV1
- **Duration:** 1 min 51 s of injected fault; 96 s to ticket
- **Service:** `dns` (CoreDNS)
- **Ticket:** `TKT-20261119-182635-1108`
- **Status:** Resolved
- **Nature:** Deliberate fault injection (game day), not a production incident

## Summary

CoreDNS was stopped for 110 seconds. `DNSFailure` fired and opened a SEV1 ticket after 96 seconds. Two other alerts (`WebDown`, `ApiDegraded`) would have fired as a consequence, but were suppressed by inhibition. This is the highest-blast-radius failure in the lab: almost everything depends on name resolution.

## Impact

- `app.local` stopped resolving for the synthetic client and for the blackbox probes.
- HTTP probes failed as a *symptom* of DNS, not because nginx was down.
- Postgres and the API stayed healthy the entire time.
- No data loss. Error budget consumed: ~1.85 min of 43 min monthly DNS budget (~4.3%).

## Detection

| Signal | Value |
| --- | --- |
| Fault injected | 18:24:59 UTC |
| Ticket opened | 18:26:35 UTC |
| Time to ticket | **96 s** |
| Alerts suppressed | `WebDown`, `ApiDegraded` |

## Timeline

| Time (UTC) | Event |
| --- | --- |
| 18:24:59 | `docker compose stop dns` — fault injected |
| 18:25:00 | Client and blackbox resolution begin failing |
| 18:26:20 | `DNSFailure` satisfies `for: 1m` and becomes active |
| 18:26:35 | Alertmanager webhook delivered; SEV1 ticket opened |
| 18:26:50 | `docker compose start dns` — recovery |
| 18:27:05 | Resolved notification |

## Root cause

CoreDNS was intentionally stopped. The exercise validates the inhibition model and the blast radius of a shared dependency.

## Contributing factors

- **Single resolver.** Both the client and blackbox use `172.28.10.53`; there is no secondary resolver.
- **Probe design.** The DNS probe targets the resolver IP directly, so it keeps working even when `app.local` is the broken record.
- **Shared dependency.** HTTP probes depend on DNS too, which is exactly why symptom suppression matters.

## What went well

- The *root cause* alert was the one that paged; the symptoms did not create noise.
- The DNS probe is independent of the HTTP probe, so the on-call can distinguish "DNS is broken" from "nginx is broken".
- Recovery was immediate and confirmed by the same probe.

## What did not go well

- The alert does not state which record failed; the on-call had to run `dig` manually.
- There is no secondary resolver, so a CoreDNS stop is a total resolution outage.
- The client has no alert of its own, so end-user impact is inferred, not measured.

## Action items

| Action | Owner | Due | Status |
| --- | --- | --- | --- |
| Include the failing record name in the alert annotation | on-call | 2026-11-26 | open |
| Evaluate a secondary resolver (dnsmasq or a second CoreDNS) | on-call | 2026-12-05 | open |
| Add a client-perspective probe (DNS + HTTP) | on-call | 2026-11-30 | open |
| Document the inhibition matrix in `docs/architecture.md` | on-call | 2026-11-19 | done |

## Lessons

1. **The first alert is not always the root cause.** Inhibition encodes that knowledge; without it, the on-call follows symptoms.
2. **Shared dependencies deserve their own probe.** Testing resolution separately from HTTP is what made the diagnosis unambiguous.
3. **Blast radius should be written down before the incident**, not discovered during it. The reachability matrix in `ip-plan.md` is the artifact that makes this explicit.
