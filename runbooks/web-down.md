# Runbook — WebDown

| | |
| --- | --- |
| **Alert** | `WebDown` |
| **Severity** | SEV1 (critical) |
| **Service** | `web` (nginx edge) |
| **SLO at risk** | Availability (99.5% / 30 days) |
| **Detected by** | `probe_success{job="blackbox-http"} == 0` for 1m |

## What it means

The synthetic HTTP probe cannot get a `200` from `http://app.local/healthz`. Either nginx is down, DNS is broken, the container is unreachable, or the host is out of resources. The probe is the user's perspective: assume user impact.

## First 2 minutes

```bash
make ps                                   # is web running?
curl -v -m 5 http://localhost:8080/healthz
docker compose logs --tail=80 web
dig @127.0.0.1 -p 15353 app.local +short  # is it DNS?
docker compose exec -T web nginx -t        # is the config valid?
df -h / ; free -h                          # is the host healthy?
```

## Diagnosis tree

```
Is `web` running?
├── no  → check exit reason: docker compose ps -a ; docker compose logs web
│         ├── OOMKilled / exit 137 → host memory pressure → see "Host resources"
│         └── config error         → nginx -t, roll back the last change
└── yes
    ├── Does `curl localhost:8080/healthz` return 200?
    │   ├── yes → the container is fine; the probe path is broken
    │   │         → check blackbox target and DNS (runbook dns-failure)
    │   └── no  → nginx or upstream problem → logs, nginx -t, /api/status
    └── Does `dig` resolve app.local?
        ├── no  → DNS failure → runbook dns-failure.md
        └── yes → inspect Docker network: docker network inspect mini-noc_frontend
```

## Remediation

| Finding | Action |
| --- | --- |
| Container stopped | `docker compose start web` |
| Bad nginx config | `git diff`, revert the change, `docker compose restart web` |
| Port conflict | `ss -tlnp \| grep 8080`; stop the conflicting process |
| Host out of memory | `docker stats --no-stream`; stop non-essential services; restart `web` |
| DNS failure | Follow `dns-failure.md`; do not restart `web` first |

Never delete volumes to "fix" an edge outage. The database is not the problem.

## Verification

```bash
make test
curl -s http://localhost:8080/healthz
curl -s http://localhost:8080/api/status | python3 -m json.tool
```

The ticket should move to `resolved` within ~30 s. If it does not, check Alertmanager:

```bash
curl -s localhost:9093/api/v2/alerts | python3 -m json.tool
```

## Escalation

- 15 minutes without recovery → escalate to the platform/network owner.
- If the cause is DNS or the host, say so explicitly in the ticket: the on-call for the next layer needs the hypothesis, not the symptom.
- If data integrity is suspected, stop and escalate before restarting anything stateful.

## Follow-up

- If the alert fired without user impact, review the probe target (is it too strict?).
- If detection took longer than 90 s, check the `for` window and scrape interval.
- Add a postmortem if the outage exceeded 5 minutes.
