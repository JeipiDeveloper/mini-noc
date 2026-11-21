#!/usr/bin/env bash
# Cenário: o serviço web cai.
# Impacto esperado: alerta WebDown (SEV1) em ~75s e 1 ticket aberto.
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-120}"

echo "[$(date -Is)] INJECT  parando o container 'web'"
docker compose stop web >/dev/null
echo "[$(date -Is)] IMPACT  http://app.local deixa de responder"
echo "[$(date -Is)] aguardando ${DURATION}s para detectar, alertar e abrir ticket..."
sleep "$DURATION"

echo "[$(date -Is)] RECOVER subindo o container 'web'"
docker compose start web >/dev/null
echo "[$(date -Is)] aguardando o alerta resolver (~45s)..."
sleep 45
echo "[$(date -Is)] FIM     veja o ticket em http://localhost:8090"
