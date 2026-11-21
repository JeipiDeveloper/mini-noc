#!/usr/bin/env bash
# Remove a latência injetada, caso o script anterior tenha sido interrompido.
set -euo pipefail
cd "$(dirname "$0")/.."

IFACE=$(docker compose exec -T web sh -c \
  'ip route get 172.28.10.1 2>/dev/null | sed -n "s/.*dev \([^ ]*\).*/\1/p"' | tr -d '\r')

echo "[$(date -Is)] removendo netem de ${IFACE:-eth0}"
docker compose exec -T web tc qdisc del dev "${IFACE:-eth0}" root >/dev/null 2>&1 || true
echo "ok"
