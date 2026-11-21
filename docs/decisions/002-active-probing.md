# ADR 002 — Active probing in addition to metrics

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Metrics answer "what does the service say about itself?". They do not answer "can a user reach it?". A process can be running, exporting healthy-looking counters, and still be unreachable because of DNS, a firewall rule, a full accept queue or a broken upstream.

NOC work is dominated by the second question.

## Decision

Use `blackbox-exporter` for three probe types, all scraped by Prometheus:

| Probe | Target | Question answered |
| --- | --- | --- |
| HTTP | `http://app.local/healthz` | Does the edge answer 200? |
| HTTP (deep) | `http://app.local/api/status` | Does the full path (nginx → API → Postgres) work? |
| DNS | `172.28.10.53` for `app.local` | Does resolution work, independently of HTTP? |
| TCP | `172.28.20.20:5432` | Is the database accepting connections? |

The probes are configured in `monitoring/blackbox.yml`; the targets and relabeling live in `monitoring/prometheus.yml`.

## Consequences

**Positive**

- Failures are detected from the same vantage point as a user (or as close as the lab allows).
- DNS and TCP failures are distinguishable from HTTP failures, which shortens triage.
- Probe duration is a direct SLI for latency, without instrumenting the application.

**Negative**

- Probes add traffic and a second service to operate.
- A probe failure is not always an application failure (it can be the probe's own network); the runbooks must include "is the probe lying?" as a step.
- `probe_success` is binary; it hides *why* it failed. `probe_http_status_code` and `probe_duration_seconds` are needed for context.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| Application metrics only | Cannot see DNS, TCP or edge failures |
| `curl` in a cron job writing to a log | No retention, no alerting, no labels, not reviewable |
| Uptime Kuma only | Good status page, weak query language and no unified alert rules |
