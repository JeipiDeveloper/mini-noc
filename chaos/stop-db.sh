#!/usr/bin/env bash
# Cenário: o Postgres cai.
# Impacto esperado: DBDown (SEV1) e ApiDegraded (SEV1) — dois sintomas,
# uma causa. O agrupamento do Alertmanager mantém os dois no mesmo ticket.
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-120}"

echo "[$(date -Is)] INJECT  parando o container 'db'"
docker compose stop db >/dev/null
echo "[$(date -Is)] IMPACT  API responde 503; /api/status fica degradado"
echo "[$(date -Is)] aguardando ${DURATION}s..."
sleep "$DURATION"

echo "[$(date -Is)] RECOVER subindo o container 'db'"
docker compose start db >/dev/null
echo "[$(date -Is)] aguardando o alerta resolver (~60s)..."
sleep 60
echo "[$(date -Is)] FIM     confira os tickets em http://localhost:8090"
