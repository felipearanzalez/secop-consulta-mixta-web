"""Ejecutar las pruebas SQL en un servidor local de PostgreSQL o PGlite Socket."""
import argparse
from functools import partial
import os
import sys
import unittest
from urllib.parse import urlsplit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pglite",action="store_true",
                        help="Adaptar solo el ensayo a las conexiones multiplexadas de PGlite Socket")
    args=parser.parse_args()
    url=os.environ.get("SECOP_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL","")
    if urlsplit(url).hostname not in {"127.0.0.1","localhost"}:
        raise SystemExit("Las pruebas requieren una base local aislada")
    if "sslmode=" not in url:
        url+=("&" if "?" in url else "?")+"sslmode=disable"
    os.environ["SECOP_TEST_DATABASE_URL"]=url
    sys.path.insert(0,os.getcwd())
    import psycopg
    connect=psycopg.connect
    if args.pglite:
        # PGlite Socket comparte una sesion subyacente. Los nombres preparados
        # por conexiones psycopg distintas pueden colisionar en ese emulador.
        # PostgreSQL nativo sigue usando la configuracion normal del driver.
        psycopg.connect=partial(connect,prepare_threshold=None)
    try:
        suite=unittest.TestSuite()
        for pattern in ["test_document_pipeline.py","test_queue_resume.py","test_phase3_review.py"]:
            suite.addTests(unittest.defaultTestLoader.discover("tests",pattern=pattern))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        psycopg.connect=connect


if __name__=="__main__":
    raise SystemExit(main())
