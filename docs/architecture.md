# Architecture

## Goal

Provide a small environment where the **operational loop** can be exercised end to end:

```
fault → detection → alert → ticket → triage (runbook) → remediation → postmortem → prevention
```

Every component exists to make one step of that loop observable or testable. Components that did not earn their place were removed (see "Out of scope").

## Components

| Component | Image / tech | Responsibility | Why it is here |
| --- | --- | --- | --- |
| `dns` | CoreDNS | Authoritative for `*.local`, forwards the rest | Name resolution must be a testable dependency |
| `web` | nginx + iproute2 | Edge: static page, `/healthz`, reverse proxy to `/api` | The only dual-homed service; the "edge router" of the lab |
| `api` | Flask + gunicorn | `/api/status` checks Postgres; `/api/slow` injects delay | Gives the database a user-visible dependency |
| `db` | Postgres 16 | Stores a seed table | Real stateful dependency, healthcheck included |
| `client` | curl loop | Generates DNS + HTTP traffic every 5 s | Produces a baseline and makes outages visible |
| `prometheus` | Prometheus | Scrapes metrics, evaluates alert rules | Single source of truth for "is it up?" |
| `blackbox` | blackbox-exporter | HTTP, DNS and TCP probes | Active probing from outside the service |
| `alertmanager` | Alertmanager | Grouping, inhibition, webhook delivery | Turns noisy alerts into actionable tickets |
| `grafana` | Grafana | Provisioned dashboards | Human-readable operational picture |
| `node-exporter` | node-exporter | Host CPU, memory, disk, network | Capacity signal independent of the app |
| `triage-bot` | Python stdlib | Alert → grouped ticket → Discord/GitHub | Closes the loop between monitoring and work |

## Network design

Two bridge networks:

- `frontend` — `172.28.10.0/24`: client, DNS, edge, monitoring stack, bot.
- `backend` — `172.28.20.0/24`: edge, API, database.

`web` is attached to both. Docker's bridge isolation prevents the client from reaching the backend directly; the only path is through nginx. This is a simplified DMZ/app-zone model, not a substitute for real VLANs or a firewall appliance.

Full addressing: [`ip-plan.md`](ip-plan.md).

## Request flow

1. `client` resolves `app.local` against CoreDNS (`172.28.10.53`).
2. `client` opens HTTP to `172.28.10.10:80` (nginx).
3. nginx serves `/healthz` locally, or proxies `/api/*` to `api:5000` over `backend`.
4. `api` opens a short-lived Postgres connection, runs `SELECT count(*)`, returns JSON.
5. If the database is unavailable, `api` returns **503** within 2 s (connect timeout).

## Monitoring flow

1. Prometheus scrapes `blackbox:9115/probe?target=...` every 15 s.
2. blackbox performs the probe and exposes `probe_success`, `probe_duration_seconds`, `probe_http_status_code`.
3. Alert rules in `monitoring/alerts.yml` evaluate every 15 s with a `for:` window.
4. Firing alerts go to Alertmanager, which groups by `cluster` + `severity` and applies inhibition.
5. Alertmanager POSTs a webhook to `triage-bot:8080/alert`.
6. The bot computes the group severity, writes a ticket event, and optionally notifies Discord / opens a GitHub Issue.
7. On recovery, Alertmanager sends the resolved payload and the bot closes the ticket.

## Failure domains

| Failure | Detected by | Alert | Ticket |
| --- | --- | --- | --- |
| nginx down | HTTP probe | `WebDown` | 1 SEV1 |
| DNS down | DNS probe | `DNSFailure` | 1 SEV1 (WebDown/ApiDegraded inhibited) |
| Postgres down | TCP probe + API probe | `DBDown` | 1 SEV1 (ApiDegraded inhibited) |
| Slow edge | probe duration | `HighLatency` | 1 SEV2 |
| Disk filling | node-exporter | `HostDiskPressure` | 1 SEV2 |

## Out of scope (deliberately)

- **High availability.** One host, one of each service.
- **Real routing protocols.** No BGP/OSPF/IS-IS. Adding them requires containerlab or VMs and is tracked as the next milestone.
- **802.1Q VLANs.** Docker bridge networks give isolation, not tagging.
- **TLS and SSO.** Local-only lab.
- **Long-term metrics.** 15-day retention, no Thanos/VictoriaMetrics.

## How this would grow

1. Replace the two Docker networks with a `containerlab` topology: 2 routers (FRR), 2 ISPs, eBGP, and a firewall.
2. Keep the same observability contract; only the probe targets change.
3. Move tickets to ServiceNow PDI by replacing `_create_issue`.
4. Add SLO burn-rate alerts on top of the existing probes.
