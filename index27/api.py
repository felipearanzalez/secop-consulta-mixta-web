"""Public, read-only evidence index API for SECOP Consulta Mixta.

No user logins, PDF uploads, credentials in browser or arbitrary upstream URL fetching.
The contracted records come only from curated or independently validated evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import threading
import time

from .store import Store, normalize_nit

ORIGIN = "https://secop-consulta-mixta-web.onrender.com"
VERSION = "2.7.0-pilot"
_lock = threading.Lock()
_counters = {}


def db_store():
    return Store(os.environ.get("DATABASE_URL"))


def initialize():
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required for persistent source indexing")
    last_error = None
    for attempt in range(8):
        try:
            s = db_store()
            try:
                s.create_schema()
                n = s.import_cases(Path(__file__).with_name("verified_cases.json"))
            finally:
                s.close()
            print("Indice documental: esquema creado, casos iniciales=" + str(n), flush=True)
            return
        except Exception as exc:
            last_error = exc
            if attempt < 7:
                time.sleep(4)
    raise RuntimeError("No se pudo iniciar el almacenamiento persistente") from last_error


def limit_ip(source):
    period = int(time.time()) // 60
    with _lock:
        stale = [k for k in _counters if k[1] < period]
        for k in stale:
            _counters.pop(k, None)
        key = (source, period)
        _counters[key] = _counters.get(key, 0) + 1
        return _counters[key] <= 90


class Handler(BaseHTTPRequestHandler):
    server_version = "SecopEvidenceIndex/2.7"

    def _send_json_headers(self, status, size):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Vary", "Origin")
        self.end_headers()

    def respond(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_json_headers(status, len(data))
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self):
        self.respond(405, {"error":"Servicio de consulta de solo lectura"})

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path not in ("/health", "/api/index/search"):
            self.respond(404, {"error":"Ruta inexistente"})
            return
        if not limit_ip(self.client_address[0]):
            self.respond(429, {"error":"Demasiadas solicitudes. Intente nuevamente en un minuto."})
            return
        try:
            if path.path == "/health":
                store = db_store()
                try:
                    count = store.rows("SELECT count(*) AS n FROM index_contracts")[0]["n"]
                finally:
                    store.close()
                self.respond(200, {"status":"ok","version":VERSION,"contract_records":count,
                                   "documents_stored":0,"coverage":"piloto"})
                return
            qs = parse_qs(path.query, keep_blank_values=True, max_num_fields=4)
            if set(qs) - {"nit"} or len(qs.get("nit",[])) != 1:
                self.respond(400,{"error":"Solo se permite el parametro nit"})
                return
            normalized = normalize_nit(qs["nit"][0])
            store = db_store()
            try:
                data = store.find(normalized)
            finally:
                store.close()
            self.respond(200,{"status":"ok","version":VERSION,**data})
        except (ValueError, TypeError):
            self.respond(400,{"error":"Ingrese un NIT colombiano valido"})
        except Exception:
            # No secrets, identifiers, or stack traces in public logs or responses.
            self.respond(503,{"error":"Indice documental temporalmente no disponible. SECOP sigue independiente."})

    def log_message(self, format, *args):
        # Deliberately avoid printing full request paths or identifiers.
        pass


def main():
    if os.environ.get('DATABASE_URL'):
        initialize()
    else:
        print('Indice preparado; falta conectar DATABASE_URL persistente',flush=True)
    port = int(os.getenv("PORT", "10000"))
    host = "0.0.0.0"
    print("Indice documental SECOP 2.7 escuchando puerto " + str(port),flush=True)
    ThreadingHTTPServer((host,port), Handler).serve_forever()


if __name__ == "__main__":
    main()
