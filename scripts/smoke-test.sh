#!/usr/bin/env bash
# Smoke test: prova, em menos de um minuto, que o laboratório está de pé.
# Use antes de gravar o GIF e antes de aplicar para uma vaga.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

PASS=0
FAIL=0

wait_for() {
  local name="$1" url="$2" tries="${3:-30}"
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS -m 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  printf "  \033[33mWAIT\033[0m  %s não respondeu em %ss\n" "$name" "$((tries * 2))"
  return 1
}

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf "  \033[32mPASS\033[0m  %s\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  \033[31mFAIL\033[0m  %s\n" "$name"
    FAIL=$((FAIL + 1))
  fi
}

echo "Mini-NOC · smoke test"
echo
echo "Aguardando os serviços (até 60s na primeira subida)..."
wait_for "web"        http://localhost:8080/healthz || true
wait_for "prometheus" http://localhost:9090/-/ready || true
wait_for "grafana"    http://localhost:3000/api/health || true
wait_for "bot"        http://localhost:8090/healthz || true
echo

check "web /healthz responde 200"        curl -fsS -m 5 http://localhost:8080/healthz
check "API /api/status responde 200"     curl -fsS -m 5 http://localhost:8080/api/status
check "Prometheus pronto"                curl -fsS -m 5 http://localhost:9090/-/ready
check "Alertmanager pronto"              curl -fsS -m 5 http://localhost:9093/-/ready
check "Grafana saudável"                 curl -fsS -m 5 http://localhost:3000/api/health
check "triage-bot saudável"              curl -fsS -m 5 http://localhost:8090/healthz

if command -v dig >/dev/null 2>&1; then
  # shellcheck disable=SC2016  # a expansão acontece dentro do bash -c
  check "DNS app.local -> 172.28.10.10"  bash -c \
    '[[ "$(dig @127.0.0.1 -p 15353 app.local +short)" == "172.28.10.10" ]]'
else
  check "DNS app.local (via container)"  bash -c \
    'docker compose exec -T client nslookup app.local | grep -q 172.28.10.10'
fi

check "cliente NÃO alcança o banco"      bash -c \
  '! docker compose exec -T client nc -z -w 3 172.28.20.20 5432'

echo
echo "  ${PASS} passaram, ${FAIL} falharam"
if [[ ${FAIL} -gt 0 ]]; then
  echo "  Dica: 'make ps' e 'make logs' mostram o que está errado."
  exit 1
fi
echo "  Tudo pronto. Rode 'make chaos-web' para gerar um incidente."
