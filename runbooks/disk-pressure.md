# Runbook — HostDiskPressure

| | |
| --- | --- |
| **Alert** | `HostDiskPressure` |
| **Severity** | SEV2 (warning) |
| **Service** | host |
| **SLO at risk** | All of them; disk exhaustion is a leading indicator of total failure |
| **Detected by** | root filesystem usage > 85% for 5m |

## What it means

The host root filesystem is above 85%. At 100%, Postgres stops accepting writes, Docker cannot create containers, and logs are lost. Act before it is full.

## First 2 minutes

```bash
df -h /
docker system df
sudo du -xh --max-depth=1 /var/lib/docker 2>/dev/null | sort -h | tail -10
docker compose logs --tail=20 | wc -c
```

## Diagnosis tree

```
What is the biggest consumer?
├── Docker images       → docker image prune (dangling only)
├── Build cache         → docker builder prune
├── Container logs      → compose already caps at 10 MB/3 files; check other log files
├── Volumes             → docker system df -v ; NEVER prune volumes blindly
├── Journal             → journalctl --disk-usage
└── User data           → find the directory, ask before deleting
```

## Safe cleanup

```bash
# Safe: removes dangling images and unused build cache
docker image prune -f
docker builder prune -f

# Safe: truncate the largest container log if it is not capped
sudo truncate -s 0 "$(docker inspect --format='{{.LogPath}}' mini-noc-prometheus)"

# Safe: vacuum the systemd journal to 500 MB
sudo journalctl --vacuum-size=500M
```

**Never run** `docker system prune -a --volumes` on a host you care about. It removes volumes, including `mini-noc_db-data`.

## Remediation

| Finding | Action |
| --- | --- |
| Dangling images / cache | `docker image prune -f && docker builder prune -f` |
| Log growth | Fix the log driver limits; truncate the current file |
| Journal | `journalctl --vacuum-size=500M` |
| Prometheus retention | Reduce `--storage.tsdb.retention.time` (currently 15d) |
| Genuinely full disk | Escalate; do not delete data to make the alert go away |

## Verification

```bash
df -h /
curl -s localhost:9090/api/v1/query --data-urlencode \
  'query=1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}'
```

The alert resolves after 5 minutes below the threshold.

## Escalation

- Above 95% → treat as SEV1: stop non-essential writers and escalate immediately.
- If the growth is unexplained, capture `du` output **before** cleaning; it is the evidence for the postmortem.

## Follow-up

- Add a second threshold at 95% mapped to SEV1.
- Add retention limits for any new volume.
- Review log driver settings for every new service in `docker-compose.yml`.
