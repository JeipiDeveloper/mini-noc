# Resume bullets

Only use numbers that exist in the repository. Every figure below is traceable to [`docs/incident-log.md`](incident-log.md) and [`docs/evidence/`](evidence/).

## Project one-liner (EN)

> **Mini-NOC** — a reproducible network operations lab with active monitoring, alert-to-ticket automation, runbooks and measured incident response. `github.com/JeipiDeveloper/mini-noc`

## Project one-liner (PT)

> **Mini-NOC** — laboratório reproduzível de operações de rede com monitoramento ativo, automação de alerta→ticket, runbooks e resposta a incidentes medida. `github.com/JeipiDeveloper/mini-noc`

## NOC / Infrastructure intern (EN)

- Built a reproducible 11-service operations lab (Docker Compose, CoreDNS, nginx, Flask, Postgres) across two isolated subnets, with one-command bootstrap and an 8-check smoke test.
- Designed 6 Prometheus/blackbox alerts across HTTP, DNS, TCP and host capacity, including severity levels, `for` windows, grouping and inhibition; one root cause produces one SEV1 ticket instead of several symptom pages.
- Automated the alert-to-ticket path with a dependency-free Python webhook service (Alertmanager → grouped ticket → optional Discord/GitHub Issues), with deduplication and resolution tracking.
- Injected 4 production-like faults (edge outage, DNS outage, database outage, 900 ms latency) and measured time-to-ticket of 90–153 s; published the raw webhook evidence, 2 blameless postmortems and 4 ADRs.
- Wrote 6 runbooks covering 100% of paging alerts, with copy-paste diagnostics, decision trees, rollback and escalation paths.

## NOC / Infrastructure intern (PT)

- Construí um laboratório reproduzível de 11 serviços (Docker Compose, CoreDNS, nginx, Flask, Postgres) em duas sub-redes isoladas, com bootstrap em um comando e smoke test de 8 checagens.
- Desenhei 6 alertas em Prometheus/blackbox para HTTP, DNS, TCP e capacidade do host, com severidade, janelas `for`, agrupamento e inibição; uma causa raiz gera um ticket SEV1 em vez de vários sintomas.
- Automatizei o caminho alerta→ticket com um serviço Python sem dependências (Alertmanager → ticket agrupado → Discord/GitHub Issues opcional), com deduplicação e rastreio de resolução.
- Injetei 4 falhas realistas (queda da borda, do DNS, do banco e 900 ms de latência) e medi tempo até o ticket de 90–153 s; publiquei a evidência bruta, 2 postmortems blameless e 4 ADRs.
- Escrevi 6 runbooks cobrindo 100% dos alertas que paginam, com diagnóstico copiável, árvores de decisão, rollback e escalonamento.

## Cloud Support / Cloud Operations (EN)

Use the same project, but lead with the dependency chain and the triage discipline:

- Operated a multi-service stack with an explicit dependency chain (DNS → edge → API → Postgres) and layered synthetic probes that distinguish a DNS failure from an application failure in under 2 minutes.
- Built the incident intake pipeline: severity classification, grouping, symptom inhibition, ticket creation, runbook attachment and resolution tracking.
- Documented blast radius and reachability matrices, and validated network segmentation (the client cannot reach the database directly).
- Measured and documented MTTD per failure mode; used the result to justify alert-window trade-offs in an ADR.

## Cover letter paragraph

> I built a small NOC in my lab because I wanted to practice the part that comes after the install. It runs a two-subnet service stack, probes it from the outside, and turns an alert into a ticket with a runbook attached. I broke it four times on purpose and measured how long detection took; the numbers, the raw webhook payloads and the postmortems are in the repository.

## What not to write

- Do not claim "production experience", "high availability" or "BGP" — the repo says otherwise, and the first interview question will expose it.
- Do not round 90 s up to "under a minute" or down to "instant".
- Do not list tools you only installed. Every tool in the bullets is used by a component you can point to.
