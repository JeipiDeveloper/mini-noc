# ADR 004 — Alert windows, grouping and inhibition

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

An alert is a promise to wake someone up. Two failure modes are equally bad:

- **Too sensitive:** pages on a single dropped packet; the on-call learns to ignore the pager.
- **Too slow:** the outage is over before anyone notices; the SLO is consumed silently.

With a 15 s scrape interval, the measured time-to-ticket in this lab was:

| Alert | `for` | Measured time to ticket |
| --- | --- | --- |
| `WebDown` | 1m | 90 s |
| `DNSFailure` | 1m | 96 s |
| `DBDown` | 1m | 101 s |
| `HighLatency` | 2m | 153 s |

The arithmetic is simply:

```
time_to_ticket ≈ for + scrape_interval + group_wait
```

## Decision

- `for: 1m` for hard availability failures (`WebDown`, `DNSFailure`, `DBDown`, `ApiDegraded`). One minute is long enough to ignore a single failed scrape, short enough to stay inside the error budget.
- `for: 2m` for `HighLatency`. Latency is noisy; a 2-minute window avoids paging on a single slow request.
- `for: 5m` for `HostDiskPressure`. Disk does not fill in seconds; a longer window reduces noise.
- `group_by: [cluster, severity]` so that alerts caused by the same event arrive in one webhook.
- **Inhibition** encodes causality:
  - `DNSFailure` inhibits `WebDown` and `ApiDegraded`;
  - `WebDown` inhibits `ApiDegraded`;
  - `DBDown` inhibits `ApiDegraded`.

The bot then opens **one ticket per group**, listing every alert and its runbook. The highest severity in the group wins.

## Consequences

**Positive**

- One root cause produces one page and one ticket, which matches how a human triages.
- The measured numbers are predictable from configuration, so the trade-off can be reviewed.
- Severity is explicit, which makes the escalation policy executable.

**Negative**

- Inhibition can hide a genuine second failure if it occurs while the source alert is firing. The runbooks must tell the on-call to check the inhibited alerts manually.
- Grouping by severity is coarse: two unrelated SEV1s in the same 30 s window share a ticket. Acceptable at this scale; a production system would group by service or by a correlation key.
- The `for` windows are a compromise tuned for a lab with a 15 s scrape interval. Changing the interval changes the effective detection time.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| `for: 0s` on everything | Pages on single-scrape noise; destroys trust in the pager |
| Static thresholds only | Simple, but blind to trends; burn-rate SLO alerts are the roadmap |
| No inhibition | Multiple pages for one cause; splits the response |
| Group by `alertname` | Produces one page per symptom, defeating the purpose |
