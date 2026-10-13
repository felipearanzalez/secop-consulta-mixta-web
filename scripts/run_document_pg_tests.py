"""Ejecutar las pruebas SQL en un servidor local de PostgreSQL o PGlite Socket."""
import os
import subprocess
import sys
from urllib.parse import urlsplit

url=os.environ.get("SECOP_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL","")
if urlsplit(url).hostname not in {"127.0.0.1","localhost"}:
    raise SystemExit("Las pruebas requieren una base local aislada")
if "sslmode=" not in url:
    url+=("&" if "?" in url else "?")+"sslmode=disable"
environment={**os.environ,"SECOP_TEST_DATABASE_URL":url}
raise SystemExit(subprocess.run([sys.executable,"-m","unittest","discover","-s","tests",
                  "-p","test_document_pipeline.py","-v"],env=environment,timeout=100).returncode)
