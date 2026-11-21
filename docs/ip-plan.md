# IP plan and ports

## Subnets

| Network | CIDR | Gateway | Purpose |
| --- | --- | --- | --- |
| `frontend` | `172.28.10.0/24` | `172.28.10.1` | Users, DNS, edge, monitoring, ticketing |
| `backend` | `172.28.20.0/24` | `172.28.20.1` | Edge, API, database |

## Addresses

### frontend

| IP | Service | Notes |
| --- | --- | --- |
| `172.28.10.1` | Docker gateway | Host side of the bridge |
| `172.28.10.10` | `web` | nginx, also on `172.28.20.10` |
| `172.28.10.20` | `client` | Synthetic traffic only |
| `172.28.10.30` | `blackbox` | Also on `172.28.20.31` |
| `172.28.10.40` | `prometheus` | |
| `172.28.10.41` | `alertmanager` | |
| `172.28.10.42` | `grafana` | |
| `172.28.10.50` | `triage-bot` | |
| `172.28.10.53` | `dns` | CoreDNS |
| `172.28.10.60` | `node-exporter` | Host metrics via mounted `/proc` and `/sys` |

### backend

| IP | Service | Notes |
| --- | --- | --- |
| `172.28.20.1` | Docker gateway | |
| `172.28.20.10` | `web` | Dual-homed edge |
| `172.28.20.20` | `db` | Postgres 5432 |
| `172.28.20.30` | `api` | gunicorn 5000 |
| `172.28.20.31` | `blackbox` | Needed for the TCP probe to the database |

## Host ports

| Host port | Container | Why |
| --- | --- | --- |
| `8080` | `web:80` | Demo application |
| `8090` | `triage-bot:8080` | Ticket queue UI |
| `3000` | `grafana:3000` | Dashboards |
| `9090` | `prometheus:9090` | Query UI / API |
| `9093` | `alertmanager:9093` | Silences and alert state |
| `15353` | `dns:53` | Avoids the host mDNS port 5353 |

## DNS records (CoreDNS `dns/hosts`)

| Name | Address |
| --- | --- |
| `app.local` | `172.28.10.10` |
| `db.local` | `172.28.20.20` |
| `grafana.local` | `172.28.10.42` |
| `prometheus.local` | `172.28.10.40` |
| `alertmanager.local` | `172.28.10.41` |
| `tickets.local` | `172.28.10.50` |

Unknown names are forwarded to `1.1.1.1` and `8.8.8.8`, so the lab can still resolve public names during triage (`curl`, package installs inside containers).

## Reachability matrix

| From \ To | app.local | api:5000 | db:5432 | internet |
| --- | --- | --- | --- | --- |
| `client` | yes | no | **no** | yes (Docker NAT) |
| `web` | yes (self) | yes | no | yes |
| `api` | no | self | yes | yes |
| `blackbox` | yes | yes (via nginx) | yes | yes |
| `prometheus` | via blackbox | via blackbox | via blackbox | yes |

`make isolation` asserts the most important row: the client cannot open a TCP connection to `172.28.20.20:5432`.
