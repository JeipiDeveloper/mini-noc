# Mini-NOC

**Um laboratório de operações de rede pequeno e reproduzível: monitoramento, alertas, tickets, runbooks e resposta a incidentes medida.**

> *English:* [README.md](README.md)

## Por que este projeto existe

A maioria dos portfólios mostra que a pessoa sabe *instalar* uma ferramenta. Este mostra o que acontece **depois**: o alerta toca, alguém precisa triar, abrir ticket, seguir um runbook, resolver e registrar o que houve.

O Mini-NOC é uma stack de serviços com duas sub-redes isoladas, instrumentada como um ambiente de produção e feita para **quebrar de propósito** — para que o ciclo operacional seja medido, não apenas afirmado.

## O que ele demonstra

- Linux e rede em containers: sub-redes, DNS, isolamento, portas.
- Monitoramento ativo: Prometheus + blackbox-exporter (HTTP, DNS, TCP).
- Desenho de alerta: severidade, janela `for`, agrupamento e inibição de sintomas.
- Automação: alerta → ticket, em Python puro (sem dependências).
- Operação: runbooks por alerta, postmortems blameless, log de incidentes.
- Reprodutibilidade: `make up`, smoke test de 8 checagens, CI no GitHub Actions.
- Relatório de uma página em PDF para anexar em candidaturas: [`docs/operations-report.pdf`](docs/operations-report.pdf).

## Como rodar

Requisitos: Docker + Compose v2, Linux, ~2 GB de RAM. Sem conta em cloud, sem custo.

```bash
cp .env.example .env      # troque as senhas
make up
make test
```

| Endpoint | URL |
| --- | --- |
| Aplicação | http://localhost:8080 |
| Fila de tickets | http://localhost:8090 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| DNS interno | `127.0.0.1:15353` |

Depois, quebre alguma coisa:

```bash
make chaos-web       # derruba o nginx por 120s → WebDown → ticket
make chaos-dns       # derruba o CoreDNS        → DNSFailure
make chaos-db        # derruba o Postgres       → DBDown
make chaos-latency   # injeta 900ms com tc      → HighLatency
```

## Incidentes medidos

Quatro falhas injetadas em 2026-11-19. Linha do tempo completa em [`docs/incident-log.md`](docs/incident-log.md); evidência bruta em [`docs/evidence/`](docs/evidence/).

| Cenário | Alerta | Sev. | Injetado (UTC) | Ticket (UTC) | Tempo até ticket |
| --- | --- | --- | --- | --- | --- |
| nginx parado | `WebDown` | SEV1 | 18:20:50 | 18:22:20 | **90 s** |
| CoreDNS parado | `DNSFailure` | SEV1 | 18:24:59 | 18:26:35 | **96 s** |
| Postgres parado | `DBDown` | SEV1 | 18:27:39 | 18:29:20 | **101 s** |
| +900 ms de latência | `HighLatency` | SEV2 | 18:30:34 | 18:33:07 | **153 s** |

O tempo até o ticket é dominado pela janela `for` do alerta (60 s para disponibilidade, 120 s para latência), mais um scrape de 15 s e o `group_wait`. É um trade-off deliberado, documentado em [`docs/decisions/004-alert-windows.md`](docs/decisions/004-alert-windows.md).

Dois comportamentos que valem notar:

- **Inibição funciona:** derrubar o DNS gerou só `DNSFailure`; `WebDown` e `ApiDegraded` foram suprimidos como sintomas.
- **Agrupamento funciona:** dois alertas críticos no mesmo grupo viram **um** ticket, com a maior severidade.

## Limitações (honestas)

- Host único: sem HA, sem failover real.
- Segmentação por redes Docker, não VLANs 802.1Q.
- Sem roteamento dinâmico (BGP/OSPF) — é o próximo passo, não uma alegação.
- Tickets em JSON local + GitHub Issues, não ServiceNow.
- Sem TLS/SSO; retenção de métricas de 15 dias.

## Estrutura

```
docker-compose.yml   Makefile   dns/   web/   api/   db/
monitoring/          bot/       chaos/ runbooks/  docs/  scripts/
```

Documentação em inglês (público-alvo: vagas nos EUA), com este resumo em português.

## Licença

MIT.
