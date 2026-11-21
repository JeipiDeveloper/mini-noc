# Incident log

All incidents below were **deliberately injected game days**, not production events. They exist to measure the operational loop and to produce evidence for the postmortems. Times are UTC.

## Method

1. Run a chaos script. It prints `INJECT`, `IMPACT` and `RECOVER` timestamps.
2. Prometheus evaluates the rule every 15 s with a `for:` window.
3. Alertmanager groups by `cluster` + `severity` and POSTs a webhook.
4. `triage-bot` records `opened_at` from the webhook payload.
5. Compare `opened_at` with the injection timestamp. The raw JSONL is in [`evidence/`](evidence/).

The clock is the same host clock for every component, so the comparison is valid to the second.

## Summary

| # | Date | Scenario | Alert | Sev. | Injected | Ticket opened | Time to ticket | Resolved notification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-19 | nginx stopped (`web`) | `WebDown` | SEV1 | 18:20:50 | 18:22:20 | 90 s | 18:24:20 |
| 2 | 2026-11-19 | CoreDNS stopped (`dns`) | `DNSFailure` | SEV1 | 18:24:59 | 18:26:35 | 96 s | 18:27:05 |
| 3 | 2026-11-19 | Postgres stopped (`db`) | `DBDown` | SEV1 | 18:27:39 | 18:29:20 | 101 s | 18:29:50 |
| 4 | 2026-11-19 | 900 ms latency on `web` | `HighLatency` | SEV2 | 18:30:34 | 18:33:07 | 153 s | 18:34:07 |

## Timeline detail

### Incident 1 — Web edge outage (injected)

- **18:20:50** — `docker compose stop web`. Edge unavailable.
- **18:22:05** — `WebDown` becomes active in Prometheus (75 s after injection: 60 s `for` + one scrape interval).
- **18:22:20** — Alertmanager delivers the webhook; ticket `TKT-20261119-182220-B0BA` opened (SEV1).
- **18:22:51** — `docker compose start web`.
- **18:23:0x** — probes recover; alert resolves.
- **18:24:20** — resolved notification delivered (still using the old 2 min `group_interval`; later reduced to 30 s).

**Observation:** `ApiDegraded` did not page, because `WebDown` inhibited it. That is the intended behaviour: one root cause, one page.

### Incident 2 — Internal DNS failure (injected)

- **18:24:59** — `docker compose stop dns`.
- **18:26:35** — ticket `TKT-20261119-182635-1108` opened (SEV1, `DNSFailure`). 96 s.
- **18:26:50** — `docker compose start dns`.
- **18:27:05** — resolved notification.

**Observation:** the blast radius is wider than the alert suggests: both `WebDown` and `ApiDegraded` would have fired, but were inhibited as symptoms. This is the correct call for paging, and a warning for triage: *the first alert is not always the root cause.*

### Incident 3 — Database outage (injected)

- **18:27:39** — `docker compose stop db`.
- **18:29:20** — ticket `TKT-20261119-182920-527F` opened (SEV1, `DBDown`). 101 s.
- **18:29:29** — `docker compose start db`.
- **18:29:50** — resolved notification.

**Observation:** `/api/status` returned 503 during the outage, as designed. `ApiDegraded` was inhibited by `DBDown`, so the on-call saw the cause, not the symptom.

### Incident 4 — Latency degradation (injected)

- **18:30:34** — `tc qdisc replace dev eth0 root netem delay 900ms` inside `web`.
- **18:33:07** — ticket `TKT-20261119-183307-D396` opened (SEV2, `HighLatency`). 153 s.
- **18:33:54** — `tc qdisc del`, latency removed.
- **18:34:07** — resolved notification.

**Observation:** this is the most realistic NOC scenario — the service is *up*, so availability alerts stay green while users are unhappy. The 2 min `for` window is the dominant term in detection time.

## What the numbers say

Time-to-ticket is almost entirely **configuration**, not code:

```
time_to_ticket ≈ for_window + scrape_interval + group_wait
  90 s  ≈ 60 s + 15 s + 15 s   (WebDown)
  96 s  ≈ 60 s + 15 s + 15 s   (DNSFailure, +6 s of scrape jitter)
 101 s  ≈ 60 s + 15 s + 15 s   (DBDown, +11 s of scrape jitter)
 153 s  ≈ 120 s + 15 s + 15 s  (HighLatency)
```

This is why [ADR 004](decisions/004-alert-windows.md) exists: detection speed is a dial you turn deliberately, with a false-positive cost.

## Open follow-ups

- [ ] Add a probe for the `client` perspective (currently the client is the only component without an alert).
- [ ] Correlate alerts with recent configuration changes (the next version of `triage-bot`).
- [ ] Add a second host and a real HA pair; the current SLO is single-host.
