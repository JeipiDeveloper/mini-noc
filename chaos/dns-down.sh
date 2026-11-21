#!/usr/bin/env bash
# Cenário: o DNS interno (CoreDNS) cai.
# Impacto esperado: DNSFailure (SEV1). WebDown e ApiDegraded são inibidos
# pela regra de inibição do Alertmanager, porque são consequência.
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-120}"

echo "[$(date -Is)] INJECT  parando o container 'dns'"
docker compose stop dns >/dev/null
echo "[$(date -Is)] IMPACT  app.local deixa de resolver para client e probes"
echo "[$(date -Is)] aguardando ${DURATION}s..."
sleep "$DURATION"

echo "[$(date -Is)] RECOVER subindo o container 'dns'"
docker compose start dns >/dev/null
echo "[$(date -Is)] aguardando o alerta resolver (~45s)..."
sleep 45
echo "[$(date -Is)] FIM     confira os tickets em http://localhost:8090"
