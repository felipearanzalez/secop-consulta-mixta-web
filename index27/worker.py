"""Bounded, incremental institutional crawl; only extracted metadata is persisted.

All NIT mentions discovered in third-party documents remain INDICIOS. Never upgrades
an entity to a consortium member without a signed contract and a verified share table.
No national coverage claim; no polling SECOP II behind authenticated sessions.
"""
from __future__ import annotations

import argparse
import sqlite3
from .store import Store, UTC


def run(source, pages=1, documents=3, pause=0.75, fetcher=None, db_url=None):
    import institutional_indexer as previous
    if source not in ("asosupro", "findeter"):
        raise ValueError("Unimplemented institutional source")
    # Transient SQLite is a processing buffer, never persisted to disk.
    transient = previous.connect_db(":memory:")
    params = {"pages":pages, "per_process":documents, "pause":pause}
    if fetcher is not None:
        params["fetcher"] = fetcher
    data = previous.crawl(transient, source, **params)
    store = Store(db_url)
    imported = 0
    try:
        store.create_schema()
        matches = transient.execute("""SELECT p.reference,p.url,d.url,e.nit,e.page,e.excerpt
             FROM identifier_evidence e JOIN documents d ON d.source=e.source AND d.url=e.doc_url
             JOIN processes p ON p.source=d.source AND p.url=d.process_url
             WHERE e.source=? ORDER BY p.reference,e.page""",(source,))
        for ref,process_url,doc_url,nit,page,excerpt in matches:
            store.upsert_indicator({"source":source, "process_ref":ref,
                                    "process_url":process_url, "document_url":doc_url,
                                    "nit":nit,"page":page,"excerpt":excerpt})
            imported += 1
        for src,url,phase,error,date in transient.execute("SELECT source,url,phase,error,at FROM incidents"):
            import hashlib
            key=hashlib.sha256((src+"|"+url+"|"+phase+"|"+date).encode()).hexdigest()
            from .store import validated_url
            if not url.startswith("https://"):
                continue
            try:
                validated_url(url)
            except ValueError:
                continue
            store.execute("INSERT INTO index_incidents (incident_key,source,stage,url,message,occurred_at) "
                          "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(incident_key) DO NOTHING",
                          (key,src,phase,url,str(error)[:220],date))
        store.con.commit()
    finally:
        store.close()
        transient.close()
    return {**data,"indicios_guardados":imported,
            "documentos_permanentemente_guardados":0,
            "nota":"Las coincidencias no verificadas NO son contratos acreditados"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",choices=["asosupro","findeter"],required=True)
    p.add_argument("--pages",type=int,default=1)
    p.add_argument("--documents",type=int,default=3)
    p.add_argument("--pause",type=float,default=0.75)
    args=p.parse_args()
    if not 1<=args.pages<=10 or not 1<=args.documents<=10 or not 0<=args.pause<=30:
        p.error("Parametros fuera de los limites de procesamiento")
    import json
    print(json.dumps(run(args.source,args.pages,args.documents,args.pause),ensure_ascii=False))


if __name__=="__main__":
    main()
