"""API do Mini-NOC.

Dois endpoints que importam para a operação:

  /api/status  -> prova que a API fala com o banco (usado pelo probe e pelo
                  alerta ApiDegraded). Devolve 503 se o banco estiver fora.
  /api/slow    -> atrasa de propósito; útil para testar latência sem mexer
                  na rede.

O objetivo não é ser uma API de negócio: é ser uma dependência observável.
"""
import os
import time

import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@app.get("/api/status")
def status():
    try:
        with psycopg2.connect(DATABASE_URL, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM service_checks")
                total = cur.fetchone()[0]
        return jsonify(status="ok", db="up", checks=total, service="mini-noc-api")
    except Exception as exc:  # noqa: BLE001 - queremos o motivo no corpo da resposta
        return (
            jsonify(status="degraded", db="down", error=str(exc)[:160]),
            503,
        )


@app.get("/api/slow")
def slow():
    ms = min(int(request.args.get("ms", 1500)), 10000)
    time.sleep(ms / 1000)
    return jsonify(ok=True, slept_ms=ms)


@app.get("/healthz")
def healthz():
    return "ok\n", 200
