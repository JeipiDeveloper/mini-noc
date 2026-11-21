# Runbook — DBDown

| | |
| --- | --- |
| **Alert** | `DBDown` |
| **Severity** | SEV1 (critical) |
| **Service** | `db` (Postgres 16) |
| **SLO at risk** | Database reachability (99.9% / 30 days) |
| **Detected by** | `probe_success{job="blackbox-tcp"} == 0` for 1m |

## What it means

The TCP handshake to `172.28.20.20:5432` failed. The API will return `503`, and `ApiDegraded` is inhibited while this alert is firing. **This is a stateful service: do not delete volumes.**

## First 2 minutes

```bash
docker compose ps db
docker compose logs --tail=120 db
docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker stats --no-stream db
df -h /var/lib/docker        # disk full is a classic Postgres killer
```

If the container is not running, `docker compose ps -a db` shows the exit code.

## Diagnosis tree

```
Is the container running?
├── no
│   ├── exit 137 / OOMKilled → host memory pressure → free memory, restart
│   ├── exit 1 with "no space" → free disk, then restart
│   └── crash loop → read the last 200 log lines; do not delete the volume
└── yes
    ├── pg_isready fails
    │   ├── "starting up"        → wait 30 s, it is still recovering
    │   ├── "no response"        → check disk, memory, and Postgres logs
    │   └── auth/role error      → credentials in .env do not match the volume
    └── pg_isready succeeds but the probe fails
        └── network path broken → check backend network and blackbox container
```

## Remediation

| Finding | Action |
| --- | --- |
| Stopped container | `docker compose start db` |
| Still starting | Wait; watch `pg_isready` until it returns "accepting connections" |
| Disk full | Free space (`docker system df`, old images), then restart |
| OOM | Reduce Postgres memory settings or free host memory, then restart |
| Bad credentials | Fix `.env` and recreate the container **without** deleting the volume |

## Data safety

- The volume is `mini-noc_db-data`. `docker compose down -v` **deletes it**. Never run it during an incident.
- There is no automated backup yet. If the volume is corrupted, the honest answer is "data loss"; escalate before attempting repair.
- Do not run `docker compose down` (even without `-v`) while the database is unhealthy; stop only the affected service.

## Verification

```bash
docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
curl -s http://localhost:8080/api/status | python3 -m json.tool   # db=up
make test
```

## Escalation

- 15 minutes without recovery → escalate to the database owner.
- If data loss is possible, say it in the ticket immediately.
- If the cause is the host (disk/memory), the platform owner owns the fix.

## Follow-up

- Add a volume backup job (pg_dump to a dated file) — currently missing.
- Add a disk-space alert specifically for `/var/lib/docker`.
- Write a postmortem if any data was lost or the outage exceeded 15 minutes.
