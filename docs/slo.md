# Service level objectives

## Scope

This SLO applies to the demo application (`app.local`), which is the only user-facing service in the lab. It is intentionally ambitious for a single-host environment; the point is to practice the mechanics of SLIs, error budgets and alerting, not to claim production resilience.

## SLIs

| SLI | Definition | Source |
| --- | --- | --- |
| Availability | successful HTTP probes to `/healthz` / total probes | `probe_success{job="blackbox-http"}` |
| Latency | probe duration for `/healthz` | `probe_duration_seconds{job="blackbox-http"}` |
| DNS resolution | successful A queries for `app.local` | `probe_success{job="blackbox-dns"}` |
| Database reachability | successful TCP handshake on 5432 | `probe_success{job="blackbox-tcp"}` |
| API correctness | `/api/status` returns 200 with `db=up` | `probe_success{job="blackbox-api"}` |

## SLOs

| SLO | Target | Window | Error budget |
| --- | --- | --- | --- |
| Availability | 99.5% | 30 days | 3 h 36 min |
| Latency (p95 < 800 ms) | 99% of minutes | 30 days | ~7 h 12 min |
| DNS resolution | 99.9% | 30 days | ~43 min |
| Database reachability | 99.9% | 30 days | ~43 min |

A 99.5% target is deliberately below "five nines": a single host cannot honestly promise more, and an SLO that is never credible is worse than no SLO.

## Alert mapping

| Alert | SLO at risk | Why this threshold |
| --- | --- | --- |
| `WebDown` | Availability | 1 min of failed probes is already 0.0023% of the monthly budget; waiting longer burns budget silently |
| `ApiDegraded` | API correctness | A 503 from `/api/status` means the user sees a broken page even if nginx is up |
| `DNSFailure` | DNS resolution | Resolution failures cascade; this is the highest-blast-radius alert |
| `DBDown` | Database reachability | The API cannot serve correct data without it |
| `HighLatency` | Latency | 800 ms is the SLO boundary; 2 min avoids paging on a single slow scrape |
| `HostDiskPressure` | All | Disk exhaustion is a leading indicator of total failure |

## Severity matrix

| Severity | Definition | Response | Update cadence |
| --- | --- | --- | --- |
| SEV1 | User-facing outage, data loss, or security exposure | Page immediately; acknowledge in 15 min | Every 30 min |
| SEV2 | Degraded performance or partial functionality | Page in business hours; acknowledge in 1 h | Every 2 h |
| SEV3 | Internal impact, no user-visible effect | Ticket, next business day | Daily |
| SEV4 | Cosmetic or documentation issue | Backlog | Weekly |

## Communication templates

**Initial (within 15 min of SEV1)**

> **SEV1 — [service] unavailable.** Impact: [what users cannot do]. Started at [UTC]. We are investigating; next update at [UTC + 30 min].

**Update**

> **Update — [service].** Current status: [mitigating / monitoring]. What we know: [one sentence]. Next update at [UTC].

**Resolution**

> **Resolved — [service].** Service restored at [UTC]. Duration: [X min]. Root cause: [one sentence]. A postmortem will follow within 48 h.

## Error budget policy

- If more than 50% of the monthly budget is consumed, freeze non-essential changes to the affected service and prioritize reliability work.
- If the budget is exhausted, only fixes and rollbacks are allowed until the next window.
- Every SEV1 consumes budget by definition; the postmortem must state how much.

## Current status

The lab is not a production service. The SLO exists to make the alert thresholds arguable, and to give the postmortems a common yardstick. Measured incidents are in [`incident-log.md`](incident-log.md).
