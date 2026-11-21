# Runbook — HighLatency

| | |
| --- | --- |
| **Alert** | `HighLatency` |
| **Severity** | SEV2 (warning) |
| **Service** | `web` (edge) |
| **SLO at risk** | p95 < 800 ms for 99% of minutes |
| **Detected by** | `probe_duration_seconds{job="blackbox-http"} > 0.8` for 2m |

## What it means

The service is **up but slow**. Availability alerts stay green, so this is the alert that catches the classic NOC complaint: "the site works, but it's slow". The cause can be DNS, the network, the edge, the API, the database, or the host.

Do not restart anything until you know *where* the time is being spent.

## First 2 minutes

```bash
# Where does the time go? (DNS, TCP connect, first byte, total)
curl -s -o /dev/null -w \
  'dns=%{time_namelookup}s connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s\n' \
  http://localhost:8080/healthz

# Is artificial latency still configured?
docker compose exec -T web tc qdisc show dev eth0

# Is the delay in the API rather than the edge?
curl -s -o /dev/null -w 'api total=%{time_total}s\n' http://localhost:8080/api/status

# Host pressure
docker stats --no-stream
uptime
df -h /
```

## Diagnosis tree

```
Is `tc qdisc` showing netem?
├── yes → someone (or a chaos script) injected latency
│         → ./chaos/reset-latency.sh ; re-test
└── no
    ├── time_namelookup is high (> 100 ms) → DNS slow → runbook dns-failure, check CoreDNS
    ├── time_connect is high             → network/TCP path → check host CPU, conntrack, MTU
    ├── time_starttransfer is high       → server processing
    │     ├── /api/status is fast but / is slow → nginx/static path
    │     └── /api/status is slow              → API or database
    │           ├── database: pg_stat_activity, locks, slow queries
    │           └── API: CPU throttling, worker count, upstream timeouts
    └── time_total is high but the rest is low → response size / client path
```

## Useful queries (Prometheus)

```promql
probe_duration_seconds{job="blackbox-http"}
histogram_quantile(0.95, rate(node_cpu_seconds_total{mode!="idle"}[5m]))
rate(node_disk_io_time_seconds_total[5m])
```

## Remediation

| Finding | Action |
| --- | --- |
| Injected `netem` | `./chaos/reset-latency.sh` |
| DNS slow | Restart CoreDNS only if it is unhealthy; otherwise investigate upstream forwarding |
| API workers saturated | `docker compose restart api` (temporary); increase gunicorn workers |
| Database slow | Check locks and long queries; do not kill sessions without confirming the impact |
| Host CPU/disk saturated | Identify the noisy container with `docker stats`; stop non-essential services |

## Verification

```bash
curl -s -o /dev/null -w 'total=%{time_total}s\n' http://localhost:8080/healthz
make test
```

Expected: well under 100 ms on localhost, and the alert resolves after the 2-minute window clears.

## Escalation

- 30 minutes without improvement → escalate to the application or platform owner.
- If latency is caused by the database, the DB owner owns the incident; link the tickets.
- If the cause is external (host provider), say so and include the measured numbers.

## Follow-up

- If the alert fired because of a chaos script left running, add a cleanup check to the demo checklist.
- Consider a p95-based alert instead of a single-probe threshold; a single probe is noisy.
- Record the latency breakdown in the ticket; it is the difference between a guess and a diagnosis.
