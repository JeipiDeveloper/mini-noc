# ADR 001 — Use CoreDNS instead of Docker's embedded DNS

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Docker Compose gives every container a resolver at `127.0.0.11` that resolves service names. That is convenient, but it cannot be **broken independently**: if a container is running, its name resolves. The lab needs name resolution to be a first-class, testable dependency, because "is it DNS?" is one of the most common NOC questions.

## Decision

Run CoreDNS as a separate service with:

- an authoritative zone for `*.local` (`dns/hosts`);
- forwarding to `1.1.1.1` / `8.8.8.8` for everything else;
- a dedicated IP (`172.28.10.53`);
- explicit `dns:` entries on the containers that must use it (`client`, `blackbox`).

## Consequences

**Positive**

- DNS can be stopped, misconfigured or slowed down without touching the application.
- The DNS probe can target the resolver by IP, so it measures resolution rather than its own dependency.
- The zone file is reviewable in a pull request, like any other configuration.
- CoreDNS is the same resolver used by Kubernetes, so the mental model transfers.

**Negative**

- One more service to run and monitor.
- Containers that need the internal zone must declare `dns:` explicitly; forgetting it produces confusing failures.
- Port 53 on the host collides with mDNS (5353 is used by Avahi), so the host port is **15353**.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| Docker embedded DNS only | Cannot be broken independently; no zone file to review |
| `dnsmasq` | Perfectly viable; CoreDNS was chosen for its declarative `Corefile` and Kubernetes relevance |
| `/etc/hosts` entries | No query logging, no failure mode, no probe target |
