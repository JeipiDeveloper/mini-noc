# Demo script — 3 minutes, no editing

Record with OBS (or `peek` on Linux) at 1440×900. Keep the browser zoom at 100%.
Do a dry run first; the point is that everything is real.

## Before recording

```bash
make down && make up          # clean start
make test                     # 8/8 green
rm -f bot/data/tickets.jsonl bot/data/state.json
```

Open three tabs, in this order:

1. `http://localhost:3000/d/mini-noc/?kiosk&from=now-15m&to=now` — dashboard
2. `http://localhost:8090` — ticket queue
3. `http://localhost:8080` — demo app

## Storyboard

| Time | Screen | What you say (short) |
| --- | --- | --- |
| 0:00–0:20 | Dashboard | "This is a two-subnet lab. Prometheus probes the edge over HTTP, DNS and TCP. Everything here is provisioned from code." |
| 0:20–0:40 | App tab | "The app depends on Postgres through an API. The client is on a different subnet, and it cannot reach the database directly." |
| 0:40–1:00 | Terminal | `make isolation` → "blocked, as expected." |
| 1:00–1:20 | Terminal | `./chaos/kill-web.sh 90` → show `INJECT` timestamp. |
| 1:20–1:50 | Dashboard | Point at the `Site (HTTP)` panel turning red and the latency timing out. |
| 1:50–2:20 | Tickets tab | Refresh: a SEV1 ticket with the alert, severity and runbook link. "Nobody typed this; Alertmanager sent a webhook and the bot built the ticket." |
| 2:20–2:40 | Runbook | Click the runbook link. "First two minutes: check the container, the config, DNS, the host." |
| 2:40–2:55 | Terminal | Script recovers the service; dashboard goes green; ticket resolves. |
| 2:55–3:00 | Close | "Detection to ticket was 90 seconds, and the number is in the repo with the raw webhook payload." |

## After recording

```bash
# Save the evidence of this run, if it differs from the committed one
cp bot/data/tickets.jsonl docs/evidence/tickets-$(date -u +%F).jsonl

# Reset the queue for the next demo
rm -f bot/data/tickets.jsonl bot/data/state.json
```

## Tips

- Do not narrate the code. Narrate the **decision** and the **measurement**.
- If something fails on camera, keep it: say "this is what triage looks like" and use the runbook. That is more credible than a perfect take.
- Keep the video under 3 minutes. Recruiters do not watch 10.
- Put the video link at the top of the README and in the resume header.
