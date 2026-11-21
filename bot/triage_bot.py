#!/usr/bin/env python3
"""triage-bot — de alerta a ticket, sem dependências externas.

Recebe o webhook do Alertmanager em POST /alert e:

  1. agrupa os alertas que chegaram juntos (uma causa raiz, vários sintomas);
  2. calcula a severidade (SEV1/SEV2/SEV3);
  3. abre UM ticket por grupo, com o link do runbook de cada alerta;
  4. notifica o Discord (se configurado);
  5. abre/comenta uma Issue no GitHub (se configurado);
  6. grava tudo em /data/tickets.jsonl e serve uma página em http://localhost:8090.

Sem DISCORD_WEBHOOK_URL e sem GITHUB_TOKEN, o bot continua funcionando:
o ticket fica registrado localmente e visível na página. Isso mantém o
laboratório reproduzível por qualquer pessoa que clonar o repositório.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
TICKETS_FILE = DATA_DIR / "tickets.jsonl"
STATE_FILE = DATA_DIR / "state.json"
RUNBOOK_DIR = Path(
    os.getenv("RUNBOOK_DIR", str(Path(__file__).resolve().parent.parent / "runbooks"))
).resolve()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()

LOCK = threading.Lock()
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
SEVERITY_LABEL = {"critical": "SEV1", "warning": "SEV2", "info": "SEV3"}
SEVERITY_COLOR = {"critical": 15158332, "warning": 16776960, "info": 3447003}
RUNBOOK_BASE = "https://github.com/{repo}/blob/main/{path}"


# ---------------------------------------------------------------------------
# Estado em disco
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _append_event(event: dict) -> None:
    with TICKETS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_events() -> list[dict]:
    if not TICKETS_FILE.exists():
        return []
    events = []
    for line in TICKETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


# ---------------------------------------------------------------------------
# Integrações
# ---------------------------------------------------------------------------
def _post_json(url: str, payload: dict, headers: dict | None = None) -> int:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def _runbook_url(path: str) -> str:
    if not path:
        return ""
    if not GITHUB_REPO:
        return path
    return RUNBOOK_BASE.format(repo=GITHUB_REPO, path=path)


def _notify_discord(ticket: dict, resolved: bool = False) -> None:
    if not DISCORD_WEBHOOK_URL:
        return

    if resolved:
        embeds = [
            {
                "title": f"RESOLVIDO · {ticket['id']}",
                "description": ticket["title"],
                "color": 3066993,
                "fields": [
                    {"name": "Aberto em", "value": ticket.get("opened_at", "-"), "inline": True},
                    {"name": "Resolvido em", "value": ticket.get("resolved_at", "-"), "inline": True},
                ],
                "footer": {"text": "Mini-NOC · triage-bot"},
            }
        ]
    else:
        embeds = []
        for alert in ticket["alerts"][:10]:
            labels = alert.get("labels", {})
            ann = alert.get("annotations", {})
            embeds.append(
                {
                    "title": f"{labels.get('alertname', '?')} · {labels.get('severity', 'info')}",
                    "description": ann.get("summary", ""),
                    "color": SEVERITY_COLOR.get(labels.get("severity", "info"), 3447003),
                    "fields": [
                        {"name": "Serviço", "value": labels.get("service", "-"), "inline": True},
                        {"name": "Runbook", "value": _runbook_url(ann.get("runbook", "")) or "-", "inline": True},
                        {"name": "Início", "value": alert.get("startsAt", "-"), "inline": False},
                    ],
                    "footer": {"text": f"Mini-NOC · {ticket['id']}"},
                }
            )

    try:
        _post_json(DISCORD_WEBHOOK_URL, {"username": "mini-noc triage-bot", "embeds": embeds})
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[warn] Discord indisponível: {exc}", flush=True)


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mini-noc-triage-bot",
    }


def _issue_body(ticket: dict) -> str:
    lines = [
        f"Ticket **{ticket['id']}** aberto automaticamente pelo `triage-bot`.",
        "",
        f"- **Severidade:** {ticket['severity_label']}",
        f"- **Início:** {ticket['opened_at']}",
        f"- **Status:** {ticket['status']}",
        "",
        "| Alerta | Serviço | Resumo | Runbook |",
        "| --- | --- | --- | --- |",
    ]
    for alert in ticket["alerts"]:
        labels = alert.get("labels", {})
        ann = alert.get("annotations", {})
        runbook = _runbook_url(ann.get("runbook", "")) or "-"
        lines.append(
            f"| `{labels.get('alertname', '?')}` | {labels.get('service', '-')} | "
            f"{ann.get('summary', '')} | {runbook} |"
        )
    lines += ["", "_Gerado pelo Mini-NOC. Feche este ticket só depois de confirmar a recuperação._"]
    return "\n".join(lines)


def _create_issue(ticket: dict) -> int | None:
    if not (GITHUB_TOKEN and "/" in GITHUB_REPO):
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    payload = {"title": f"[{ticket['severity_label']}] {ticket['title']}", "body": _issue_body(ticket)}
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=_github_headers(), method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()).get("number")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"[warn] GitHub indisponível: {exc}", flush=True)
        return None


def _comment_issue(number: int, body: str) -> None:
    if not (GITHUB_TOKEN and number):
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{number}/comments"
    try:
        _post_json(url, {"body": body}, _github_headers())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[warn] comentário no GitHub falhou: {exc}", flush=True)


# ---------------------------------------------------------------------------
# Lógica de ticket
# ---------------------------------------------------------------------------
def _severity(alerts: list[dict]) -> str:
    worst = "info"
    for alert in alerts:
        sev = alert.get("labels", {}).get("severity", "info")
        if SEVERITY_RANK.get(sev, 9) < SEVERITY_RANK.get(worst, 9):
            worst = sev
    return worst


def _ticket_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"TKT-{stamp}-{random.randint(0x1000, 0xFFFF):04X}"


def _new_ticket(payload: dict, alerts: list[dict]) -> dict:
    severity = _severity(alerts)
    names = sorted({a.get("labels", {}).get("alertname", "?") for a in alerts})
    title = ", ".join(names) if names else "Alerta sem nome"
    return {
        "id": _ticket_id(),
        "group_key": payload.get("groupKey", ""),
        "severity": severity,
        "severity_label": SEVERITY_LABEL.get(severity, "SEV3"),
        "title": title,
        "status": "firing",
        "opened_at": _now_iso(),
        "resolved_at": None,
        "alerts": alerts,
    }


def handle_alert(payload: dict) -> dict:
    alerts = payload.get("alerts", []) or []
    firing = [a for a in alerts if a.get("status") == "firing"]
    resolved = [a for a in alerts if a.get("status") == "resolved"]
    group_key = payload.get("groupKey") or hashlib.sha1(
        json.dumps(sorted(a.get("fingerprint", "") for a in alerts)).encode()
    ).hexdigest()

    with LOCK:
        state = _load_state()
        entry = state.get(group_key)

        # --- Resolução -------------------------------------------------------
        if not firing and resolved:
            if not entry or entry.get("status") != "firing":
                return {"ok": True, "ignored": "resolved sem ticket aberto"}
            ticket = entry["ticket"]
            ticket.update(status="resolved", resolved_at=_now_iso())
            _append_event(
                {
                    "type": "resolved",
                    "ticket_id": ticket["id"],
                    "ts": ticket["resolved_at"],
                    "title": ticket["title"],
                    "severity": ticket["severity"],
                    "severity_label": ticket["severity_label"],
                    "alerts": ticket["alerts"],
                }
            )
            _notify_discord(ticket, resolved=True)
            _comment_issue(
                entry.get("github_issue"),
                f"**Resolvido** em {ticket['resolved_at']}.\n\n"
                "Confirme no Grafana e escreva o postmortem em `docs/postmortems/`.",
            )
            entry.update(status="resolved", ticket=ticket)
            state[group_key] = entry
            _save_state(state)
            return {"ok": True, "ticket": ticket["id"], "status": "resolved"}

        # --- Abertura / atualização -----------------------------------------
        if not entry or entry.get("status") != "firing":
            ticket = _new_ticket(payload, firing)
            entry = {"status": "firing", "ticket": ticket, "github_issue": None}
            _append_event(
                {
                    "type": "opened",
                    "ticket_id": ticket["id"],
                    "ts": ticket["opened_at"],
                    "title": ticket["title"],
                    "severity": ticket["severity"],
                    "severity_label": ticket["severity_label"],
                    "alerts": ticket["alerts"],
                }
            )
            issue = _create_issue(ticket)
            entry["github_issue"] = issue
            if issue:
                _append_event(
                    {"type": "github", "ticket_id": ticket["id"], "ts": _now_iso(), "issue": issue}
                )
            _notify_discord(ticket)
            state[group_key] = entry
            _save_state(state)
            return {"ok": True, "ticket": ticket["id"], "status": "opened", "issue": issue}

        # Já existe ticket firing: registra atualização sem duplicar.
        ticket = entry["ticket"]
        known = {a.get("fingerprint") for a in ticket["alerts"]}
        fresh = [a for a in firing if a.get("fingerprint") not in known]
        if fresh:
            ticket["alerts"].extend(fresh)
            ticket["severity"] = _severity(ticket["alerts"])
            ticket["severity_label"] = SEVERITY_LABEL.get(ticket["severity"], "SEV3")
            _append_event(
                {
                    "type": "updated",
                    "ticket_id": ticket["id"],
                    "ts": _now_iso(),
                    "title": ticket["title"],
                    "severity": ticket["severity"],
                    "severity_label": ticket["severity_label"],
                    "alerts": fresh,
                }
            )
            _notify_discord(ticket)
            entry["ticket"] = ticket
            state[group_key] = entry
            _save_state(state)
            return {"ok": True, "ticket": ticket["id"], "status": "updated", "new_alerts": len(fresh)}

        return {"ok": True, "ticket": ticket["id"], "status": "unchanged"}


# ---------------------------------------------------------------------------
# Visualização
# ---------------------------------------------------------------------------
def _tickets_view() -> list[dict]:
    tickets: dict[str, dict] = {}
    for event in _read_events():
        tid = event.get("ticket_id")
        if not tid:
            continue
        if tid not in tickets:
            tickets[tid] = {
                "id": tid,
                "title": event.get("title", ""),
                "severity": event.get("severity", "info"),
                "severity_label": event.get("severity_label", "SEV3"),
                "status": "firing",
                "opened_at": event.get("ts", ""),
                "resolved_at": None,
                "alerts": [],
                "updates": 0,
            }
        ticket = tickets[tid]
        if event.get("type") == "opened":
            ticket["opened_at"] = event.get("ts", ticket["opened_at"])
            ticket["alerts"] = event.get("alerts", [])
        elif event.get("type") == "updated":
            ticket["updates"] += 1
            ticket["alerts"].extend(event.get("alerts", []))
        elif event.get("type") == "resolved":
            ticket["status"] = "resolved"
            ticket["resolved_at"] = event.get("ts")
    return sorted(tickets.values(), key=lambda t: t["opened_at"], reverse=True)


def _render_html() -> str:
    rows = []
    for t in _tickets_view()[:100]:
        cls = "crit" if t["severity"] == "critical" else "warn" if t["severity"] == "warning" else "info"
        runbooks = sorted(
            {
                html.escape(a.get("annotations", {}).get("runbook", ""))
                for a in t["alerts"]
                if a.get("annotations", {}).get("runbook")
            }
        )
        rb = " ".join(
            f'<a href="/runbook/{r.split("/")[-1]}">{r.split("/")[-1]}</a>' for r in runbooks
        ) or "-"
        status = "ABERTO" if t["status"] == "firing" else "RESOLVIDO"
        rows.append(
            f"<tr><td class='mono'>{html.escape(t['id'])}</td>"
            f"<td><span class='badge {cls}'>{t['severity_label']}</span> {html.escape(t['title'])}"
            f"<div class='sub'>{len(t['alerts'])} alerta(s) · {t['updates']} atualização(ões) · {rb}</div></td>"
            f"<td><span class='status {t['status']}'>{status}</span></td>"
            f"<td class='mono'>{html.escape(t['opened_at'])}</td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='4' class='empty'>Nenhum ticket ainda. Rode <code>make chaos-web</code>.</td></tr>")

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mini-NOC · tickets</title>
<style>
:root{{--bg:#0b0f14;--panel:#121b27;--line:#1e2a3a;--text:#e6edf3;--muted:#8b98a9}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:ui-sans-serif,system-ui,sans-serif;padding:32px}}
main{{max-width:1080px;margin:0 auto}}
h1{{font-size:24px;margin:0 0 4px;letter-spacing:-.02em}}
.sub{{color:var(--muted);font-size:13px;margin:0 0 24px}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:12px 14px;border-bottom:1px solid var(--line)}}
td{{padding:12px 14px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.mono{{font-family:ui-monospace,monospace;font-size:12px;color:var(--muted);white-space:nowrap}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;margin-right:6px}}
.crit{{background:#4a1111;color:#ff8a80}}
.warn{{background:#4a3a0a;color:#ffd54f}}
.info{{background:#0f2a44;color:#82b1ff}}
.status{{font-size:11px;font-weight:700;letter-spacing:.06em}}
.status.firing{{color:#ff8a80}}
.status.resolved{{color:#69f0ae}}
.empty{{color:var(--muted);text-align:center;padding:28px}}
a{{color:#6cb6ff;text-decoration:none}}
a:hover{{text-decoration:underline}}
code{{background:#0a1018;padding:2px 6px;border-radius:6px;font-size:12px}}
</style></head><body><main>
<h1>Mini-NOC · tickets</h1>
<p class="sub">Cada linha é um grupo de alertas. A severidade mais alta do grupo define o ticket.
Atualize a página após rodar um cenário de caos.</p>
<table><thead><tr><th>Ticket</th><th>Descrição</th><th>Status</th><th>Aberto em (UTC)</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</main></body></html>"""


def _render_runbook(path: str) -> str | None:
    name = Path(path).name
    candidate = (RUNBOOK_DIR / name).resolve()
    if RUNBOOK_DIR not in candidate.parents or not candidate.is_file():
        return None
    text = candidate.read_text(encoding="utf-8")
    body = html.escape(text)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>{html.escape(path)}</title><style>
body{{background:#0b0f14;color:#e6edf3;font-family:ui-sans-serif,system-ui,sans-serif;padding:32px;max-width:900px;margin:0 auto}}
pre{{white-space:pre-wrap;background:#121b27;border:1px solid #1e2a3a;border-radius:12px;padding:20px;line-height:1.6;font-size:13px}}
a{{color:#6cb6ff}}
</style></head><body><p><a href="/">← tickets</a></p><pre>{body}</pre></body></html>"""


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "mini-noc-triage-bot/1.0"

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict | list) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/tickets"):
            self._send(200, _render_html().encode(), "text/html; charset=utf-8")
        elif self.path == "/tickets.json":
            self._json(200, _tickets_view())
        elif self.path == "/healthz":
            self._send(200, b"ok\n", "text/plain")
        elif self.path.startswith("/runbook/"):
            page = _render_runbook(self.path.removeprefix("/runbook/"))
            if page is None:
                self._send(404, b"runbook nao encontrado\n", "text/plain")
            else:
                self._send(200, page.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found\n", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/alert":
            self._send(404, b"not found\n", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "json inválido"})
            return
        try:
            result = handle_alert(payload)
        except Exception as exc:  # noqa: BLE001 - o webhook nunca deve derrubar o bot
            print(f"[error] falha ao processar alerta: {exc}", flush=True)
            self._json(500, {"ok": False, "error": str(exc)[:200]})
            return
        self._json(200, result)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[http] {self.address_string()} {fmt % args}", flush=True)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"triage-bot ouvindo em :{port} (data={DATA_DIR})", flush=True)
    print(f"discord={'on' if DISCORD_WEBHOOK_URL else 'off'} github={'on' if GITHUB_TOKEN else 'off'}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
