# Runbook — DNSFailure

| | |
| --- | --- |
| **Alert** | `DNSFailure` |
| **Severity** | SEV1 (critical) |
| **Service** | `dns` (CoreDNS) |
| **SLO at risk** | DNS resolution (99.9% / 30 days) |
| **Detected by** | `probe_success{job="blackbox-dns"} == 0` for 1m |

## What it means

CoreDNS did not answer an `A` query for `app.local` with `NOERROR`. This is the highest-blast-radius alert in the lab: HTTP and API probes depend on resolution, and those alerts are **inhibited** while this one is firing. Fix DNS first.

## First 2 minutes

```bash
dig @127.0.0.1 -p 15353 app.local +short
dig @127.0.0.1 -p 15353 db.local +short
dig @127.0.0.1 -p 15353 example.com +short     # forwarding still works?
docker compose ps dns
docker compose logs --tail=80 dns
```

Expected healthy output: `172.28.10.10` for `app.local`, `172.28.20.20` for `db.local`.

## Diagnosis tree

```
Does dig time out?
├── yes → the resolver is not answering
│     ├── container stopped → docker compose start dns
│     ├── port conflict      → ss -tlnp | grep 15353
│     └── crash loop         → logs; validate the Corefile
└── no, but NXDOMAIN for app.local
      ├── record missing from dns/hosts → add it, restart dns
      ├── typo in the Corefile zone      → fix, restart dns
      └── wrong file mounted             → docker compose config | grep -A3 dns
```

## Validate before restarting

```bash
# CoreDNS has no shell in the official image; check config from the host
docker compose config | sed -n '/dns:/,/^[a-z]/p'
cat dns/Corefile dns/hosts

# Confirm the container's IP is the one the probes use
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' mini-noc-dns
```

## Remediation

| Finding | Action |
| --- | --- |
| Container stopped | `docker compose start dns` |
| Bad record | Edit `dns/hosts`, then `docker compose restart dns` |
| Bad Corefile | Fix the block, restart; the process fails fast on syntax errors |
| Port 15353 taken | `ss -tlnp \| grep 15353`; free the port or change the mapping |

Do **not** restart `web`, `api` or `db` while DNS is broken: you will add noise and may lose the evidence.

## Verification

```bash
dig @127.0.0.1 -p 15353 app.local +short   # 172.28.10.10
make test
```

Inhibition should clear automatically; `WebDown`/`ApiDegraded` should not page.

## Escalation

- 10 minutes without resolution → escalate to the network/DNS owner.
- If public names also fail, forwarding is broken (upstream or egress), not the internal zone. Say that explicitly.
- If the resolver is being restarted repeatedly, capture two crash logs before the next restart.

## Follow-up

- Add the failing record name to the alert annotation.
- Consider a secondary resolver; today there is a single point of failure.
- If the failure was caused by a config change, add the change to the ticket and write a postmortem.
