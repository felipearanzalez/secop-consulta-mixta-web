"""API experimental de consulta de evidencia y cobertura; no modifica la web 2.10."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from urllib.parse import parse_qs,urlsplit

from index28.persistence import DocumentStore

VERSION="2.11-r2"
ORIGIN="https://secop-consulta-mixta-web.onrender.com"


def build_handler(database_url: str,origin: str=ORIGIN):
    """Una conexion por solicitud; sin claves, uploads o URLs arbitrarias."""
    class Handler(BaseHTTPRequestHandler):
        server_version="SecopDocumentaryPilot/2.11"

        def respond(self,status:int,payload:dict):
            body=json.dumps(payload,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Access-Control-Allow-Origin",origin)
            self.send_header("Vary","Origin")
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            store=None
            try:
                path=urlsplit(self.path)
                if path.path not in {"/health","/api/documentary/status","/api/documentary/search"}:
                    self.respond(404,{"error":"Ruta inexistente"});return
                params=parse_qs(path.query,keep_blank_values=True,max_num_fields=3)
                if path.path!="/api/documentary/search":
                    if params:
                        self.respond(400,{"error":"Ruta sin parametros"});return
                elif set(params)-{"nit","limit"} or len(params.get("nit",[]))!=1 or len(params.get("limit",["100"]))!=1:
                    self.respond(400,{"error":"Se requiere un NIT y un limite opcional"});return
                store=DocumentStore(database_url)
                coverage=store.overview()
                metadata={"version":VERSION,"checked_at":datetime.now(timezone.utc).isoformat(),
                          "national_coverage":False,"scope":"Piloto documental; no certifica ausencia de contratos"}
                if path.path=="/api/documentary/search":
                    limit=int(params.get("limit",["100"])[0])
                    if not 1<=limit<=200:
                        raise ValueError("Limite invalido")
                    observations=store.candidates(params["nit"][0],limit=limit)
                    self.respond(200,{"status":"ok",**metadata,**observations,"coverage":coverage})
                else:
                    self.respond(200,{"status":"ok",**metadata,"coverage":coverage})
            except (ValueError,TypeError):
                self.respond(400,{"error":"Parametros invalidos"})
            except Exception:
                self.respond(503,{"error":"Indice experimental no disponible; no se presume ausencia de contratos"})
            finally:
                if store:
                    store.close()

        def do_POST(self):
            self.respond(405,{"error":"Servicio de solo lectura"})

        do_PUT=do_POST
        do_DELETE=do_POST
        do_PATCH=do_POST

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin",origin)
            self.send_header("Access-Control-Allow-Methods","GET, OPTIONS")
            self.end_headers()

        def log_message(self,*args):
            pass
    return Handler


def main(argv=None):
    parser=argparse.ArgumentParser(description="Servidor de lectura del piloto documental")
    parser.add_argument("--database",required=True,help="URL de base de desarrollo")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=10001)
    args=parser.parse_args(argv)
    store=DocumentStore(args.database)
    try:store.create_document_schema()
    finally:store.close()
    ThreadingHTTPServer((args.host,args.port),build_handler(args.database)).serve_forever()


if __name__=="__main__":main()
