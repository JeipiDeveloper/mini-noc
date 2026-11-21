# Evidence — game day 2026-11-19

Raw webhook data captured by `triage-bot` during the four fault injections.
This is the source of truth behind the numbers in [`incident-log.md`](../incident-log.md) and the postmortems.

## Files

| File | Description | SHA-256 |
| --- | --- | --- |
| `tickets-2026-11-19.jsonl` | Append-only event log: `opened`, `updated`, `resolved` | `28c5d0de1f6c0fc7238c8f2c96d6ac14645eaf2a7cb549a3c559f06bef811f25` |
| `state-2026-11-19.json` | Group key → ticket state at the end of the run | `46adfec07520e82a4c95790c8878f3bc50b1d178ca401146a87be517c0d8a331` |

## Format

One JSON object per line:

```json
{
  "type": "opened",
  "ticket_id": "TKT-20261119-182220-B0BA",
  "ts": "2026-11-19T18:22:20+00:00",
  "title": "WebDown",
  "severity": "critical",
  "severity_label": "SEV1",
  "alerts": [
    {
      "status": "firing",
      "labels": { "alertname": "WebDown", "severity": "critical", "service": "web" },
      "annotations": { "summary": "Site fora do ar (app.local/healthz)", "runbook": "runbooks/web-down.md" },
      "startsAt": "2026-11-19T18:22:05.059Z",
      "fingerprint": "43b84a80e3bb9d3d"
    }
  ]
}
```

`ts` is written when the bot receives the webhook. `startsAt` is Prometheus' alert start time, which is the more precise detection timestamp.

## How to reproduce

```bash
make up
make test
rm -f bot/data/tickets.jsonl bot/data/state.json   # start clean
make chaos-web
make tickets
```

Compare the script's `INJECT` timestamp with `opened_at` / `startsAt`.

## Integrity check

```bash
sha256sum docs/evidence/tickets-2026-11-19.jsonl
# expected: 28c5d0de1f6c0fc7238c8f2c96d6ac14645eaf2a7cb549a3c559f06bef811f25
```

## Notes

- Discord and GitHub integrations were **not** configured during this run, so the tickets exist only in the local JSONL and the web UI. That is intentional: the lab must work without credentials.
- The first incident's resolved notification took 2 minutes because `group_interval` was still 120 s. It was changed to 30 s before the second incident.
