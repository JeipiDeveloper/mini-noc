#!/usr/bin/env bash
# Cenário: latência alta (900 ms) na saída do container web.
# Impacto esperado: HighLatency (SEV2) após 2 minutos, sem derrubar o serviço.
# É o cenário mais próximo de um problema real de NOC: "está lento, mas está no ar".
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-180}"
DELAY="${2:-900ms}"

IFACE=$(docker compose exec -T web sh -c \
  'ip route get 172.28.10.1 2>/dev/null | sed -n "s/.*dev \([^ ]*\).*/\1/p"' | tr -d '\r')

if [[ -z "${IFACE}" ]]; then
  echo "ERRO: não consegui descobrir a interface de rede do container web" >&2
  exit 1
fi

cleanup() {
  echo "[$(date -Is)] CLEANUP removendo netem de ${IFACE}"
  docker compose exec -T web tc qdisc del dev "${IFACE}" root >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[$(date -Is)] INJECT  adicionando ${DELAY} de atraso em ${IFACE}"
docker compose exec -T web tc qdisc replace dev "${IFACE}" root netem delay "${DELAY}"
echo "[$(date -Is)] IMPACT  o site continua no ar, mas lento"
echo "[$(date -Is)] aguardando ${DURATION}s para o alerta HighLatency disparar..."
sleep "$DURATION"

echo "[$(date -Is)] RECOVER removendo a latência"
cleanup
trap - EXIT
echo "[$(date -Is)] aguardando o alerta resolver (~45s)..."
sleep 45
echo "[$(date -Is)] FIM     confira os tickets em http://localhost:8090"
