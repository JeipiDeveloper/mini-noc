SHELL := /bin/bash
COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help env up down clean ps logs test urls tickets dig isolation \
        chaos-web chaos-dns chaos-db chaos-latency reset-latency

help: ## Mostra os comandos disponíveis
	@echo "Mini-NOC — comandos"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo

env: .env ## Cria o .env a partir do exemplo

.env:
	@cp .env.example .env
	@echo "→ .env criado. Edite as senhas antes de expor este lab na internet."

up: env ## Sobe tudo (build + containers)
	$(COMPOSE) up -d --build
	@echo
	@echo "Aguardando os serviços ficarem prontos (~30s)..."
	@sleep 20
	@$(MAKE) --no-print-directory urls

down: ## Para os containers (mantém volumes)
	$(COMPOSE) down

clean: ## Para tudo e apaga volumes (perde métricas e tickets)
	$(COMPOSE) down -v --remove-orphans

ps: ## Estado dos containers
	$(COMPOSE) ps

logs: ## Logs de todos os serviços
	$(COMPOSE) logs -f --tail=60

urls: ## Mostra as URLs do laboratório
	@echo "  App .............. http://localhost:8080"
	@echo "  Tickets .......... http://localhost:8090"
	@echo "  Grafana .......... http://localhost:3000  (admin / ver .env)"
	@echo "  Prometheus ....... http://localhost:9090"
	@echo "  Alertmanager ..... http://localhost:9093"
	@echo "  DNS interno ...... 127.0.0.1:15353"

test: ## Roda o smoke test de ponta a ponta
	./scripts/smoke-test.sh

dig: ## Consulta o DNS interno
	@dig @127.0.0.1 -p 15353 app.local +short || \
		docker compose exec -T client nslookup app.local

isolation: ## Prova que o cliente não alcança o banco direto
	@echo "→ cliente ($(shell echo 172.28.10.20)) tentando TCP no banco (172.28.20.20:5432)"
	@docker compose exec -T client sh -c 'nc -z -w 3 172.28.20.20 5432 && echo "FALHA DE SEGMENTAÇÃO" || echo "BLOQUEADO (esperado)"'

tickets: ## Lista os tickets em JSON
	@curl -s http://localhost:8090/tickets.json | python3 -m json.tool

chaos-web: ## Cenário: site fora do ar
	./chaos/kill-web.sh

chaos-dns: ## Cenário: DNS interno fora do ar
	./chaos/dns-down.sh

chaos-db: ## Cenário: banco de dados fora do ar
	./chaos/stop-db.sh

chaos-latency: ## Cenário: latência alta no site
	./chaos/latency.sh

reset-latency: ## Remove a latência injetada
	./chaos/reset-latency.sh
