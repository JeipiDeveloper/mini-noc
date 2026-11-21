# Runbook — ApiDegraded

| | |
| --- | --- |
| **Alert** | `ApiDegraded` |
| **Severity** | SEV1 (critical) |
| **Service** | `api` (Flask) |
| **SLO at risk** | API correctness |
| **Detected by** | `probe_success{job="blackbox-api"} == 0` for 1m |

## What it means

`/api/status` did not return `200`. In this lab the endpoint returns `503` when it cannot reach Postgres, so the most likely cause is the database. It can also be the API process itself, a bad deploy, or a timeout.

> **Note:** this alert is inhibited by `WebDown` and `DBDown`. If you are reading this because the alert fired, the cause is *not* the edge or the database — look at the API process itself.

## First 2 minutes

```bash
curl -s -i http://localhost:8080/api/status
docker compose logs --tail=100 api
docker compose ps api
docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker stats --no-stream api db
```

## Diagnosis tree

```
Does /api/status return 503 with "db": "down"?
├── yes → the API is healthy, the database is not → runbook db-down.md
└── no
    ├── connection refused / timeout → API process down or port not listening
    │     → docker compose ps api ; logs ; restart
    ├── 500 with a Python traceback → application bug or bad config
    │     → read the traceback, check DATABASE_URL, roll back if recent
    └── 200 but slow (> 1s) → latency problem → runbook high-latency.md
```

## Useful commands

```bash
# Test the database path from inside the API container
docker compose exec -T api python - <<'PY'
import os, psycopg2
print(psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=2).status)
PY

# Check the effective environment (never print secrets in a ticket)
docker compose exec -T api sh -c 'echo ${DATABASE_URL%%@*}@***'
```

## Remediation

| Finding | Action |
| --- | --- |
| Database unreachable | Follow `db-down.md`; do not restart the API first |
| API crashed | `docker compose restart api`; check logs for the exit reason |
| Bad deploy | Revert the image/config change, then restart |
| Credential mismatch | Fix `.env`, `docker compose up -d api` |

## Verification

```bash
curl -s http://localhost:8080/api/status | python3 -m json.tool   # expect db=up
make test
```

## Escalation

- 15 minutes without recovery → escalate to the application owner.
- If the database is the cause, the DB owner owns the incident; keep this ticket linked to it.
- If a deploy is implicated, include the commit hash in the ticket.

## Follow-up

- If `ApiDegraded` fired while the database was already down, the inhibition rule failed. Check `alertmanager.yml`.
- Add a unit test for `/api/status` that asserts `503` when the DSN is invalid.
