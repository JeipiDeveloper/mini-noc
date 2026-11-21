# ADR 003 — Local tickets by default, GitHub Issues when configured

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

The operational loop is only complete when an alert becomes a **tracked piece of work** with an owner and a history. Real NOCs use ServiceNow, Jira Service Management, Remedy or similar. Those tools require accounts, tenants or a personal developer instance, which makes a portfolio project hard to reproduce.

A project that only works with a paid account is a project nobody will run.

## Decision

`triage-bot` writes every ticket to `/data/tickets.jsonl` and serves a small HTML queue at `:8090`. Two optional integrations are enabled by environment variables:

- `DISCORD_WEBHOOK_URL` — posts a rich embed when a ticket opens or resolves.
- `GITHUB_TOKEN` + `GITHUB_REPO` — opens one Issue per ticket group and comments on resolution.

The GitHub integration is isolated in `_create_issue` / `_comment_issue`, so substituting ServiceNow or Jira is a small, contained change.

## Consequences

**Positive**

- `git clone && make up` produces a working ticket queue with no credentials.
- The JSONL file is the audit trail used by the incident log; it is copied to `docs/evidence/`.
- The webhook contract is the Alertmanager standard, so the bot is portable.

**Negative**

- GitHub Issues is not an ITIL tool: no SLA fields, no on-call rotation, no CMDB.
- The local JSONL is single-writer; it is not a database and would not survive concurrency at scale.
- Discord is a notification channel, not an escalation policy.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| ServiceNow PDI only | Requires account setup; breaks reproducibility for reviewers |
| Jira Cloud free tier | Same problem, plus OAuth configuration |
| No ticketing at all | The loop would stop at "alert", which is exactly the gap this project addresses |
