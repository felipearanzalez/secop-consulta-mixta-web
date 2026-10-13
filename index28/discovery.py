"""Barrido acotado de contratistas plurales SECOP I, sin conocer el NIT integrante.

El cursor avanza solo despues de persistir el inventario completo y sus trabajos
documentales. Un barrido no demuestra cobertura nacional ni ejecucion actual.
"""
from __future__ import annotations
import re
from urllib.parse import urlencode

from index28.persistence import DocumentStore
from index28.socrata import fetch_json,VALID_CONSTANCIA,BASE
from index28.expediente_secop_i import expediente
from index28.pipeline import priority
from index28 import checkpoints

UID=re.compile(r"\d{2}-\d{1,2}-\d{1,14}(?:-\d{1,14})?\Z")
DATASETS={"f789-7hwg","qddk-cgux"}


def discovery_url(dataset: str, cursor: str = "", limit: int = 10) -> str:
    if dataset not in DATASETS or not 1<=limit<=100 or (cursor and not UID.fullmatch(cursor)):
        raise ValueError("Fuente, cursor o limite de descubrimiento invalido")
    field="upper(nom_razon_social_contratista)"
    predicate="("+" OR ".join(field+" like '"+p+"'" for p in
              ("%CONSORC%","%UNION TEMPORAL%","%UNIÓN TEMPORAL%","UT %","U.T.%"))+")"
    where="uid IS NOT NULL AND numero_de_constancia IS NOT NULL AND "+predicate
    if cursor:
        where+=" AND uid > '"+cursor+"'"
    return BASE+"/"+dataset+".json?"+urlencode({"$select":"uid,numero_de_constancia,nom_razon_social_contratista",
          "$where":where,"$order":"uid ASC","$limit":limit})


def seed_plural(store: DocumentStore, *, dataset: str = "f789-7hwg", partition: str = "plural_initial",
                limit: int = 10, fetch=fetch_json, inventory_fn=expediente) -> dict:
    store.create_document_schema();checkpoints.ensure_schema(store)
    checkpoint=checkpoints.read(store,dataset,partition)
    cursor=(checkpoint or {}).get("cursor","")
    url=discovery_url(dataset,cursor,limit)
    try:
        rows=fetch(url)
        if not isinstance(rows,list) or len(rows)>limit or any(not isinstance(r,dict) for r in rows):
            raise ValueError("Respuesta no valida para el barrido")
        # No se acepta un cursor desordenado, repetido ni ajeno al esquema publicado.
        uids=[str(r.get("uid") or "") for r in rows]
        if any(not UID.fullmatch(uid) or (cursor and uid<=cursor) for uid in uids) or uids!=sorted(set(uids)):
            raise ValueError("Orden o identidad de registros no verificable")
    except Exception:
        checkpoints.record(store,dataset,partition,status="failed",count=0,error="discovery_source_failed")
        return {"status":"failed","dataset":dataset,"persisted_processes":0,"cursor":cursor,
                "error":"discovery_source_failed","national_coverage":False}
    output=[]
    completed=cursor
    seen=set()
    for row in rows:
        reference=str(row.get("numero_de_constancia") or "")
        if not VALID_CONSTANCIA.fullmatch(reference):
            checkpoints.record(store,dataset,partition,status="partial",count=len(output),error="invalid_process_reference")
            return {"status":"partial","dataset":dataset,"persisted_processes":len(output),
                    "cursor":completed,"processes":output,"national_coverage":False}
        try:
            if reference not in seen:
                inventory=inventory_fn(reference,fetch=fetch)
                if inventory.get("platform")!="SECOP I" or inventory.get("reference")!=reference:
                    raise ValueError("Inventario de otro proceso")
                snapshot=store.save_inventory(inventory)
                jobs=[store.enqueue("SECOP I",reference,doc,priority(doc)) for doc in inventory["document_metadata"]]
                if not inventory["complete_in_requested_sources"]:
                    raise ValueError("Inventario parcial")
                output.append({"reference":reference,"inventory_key":snapshot,"documents_queued":len(jobs),
                               "member_contracts_verified":0})
                seen.add(reference)
            completed=str(row["uid"])
            checkpoints.record(store,dataset,partition,status="ok",count=len(output),cursor=completed)
        except Exception:
            # Los trabajos ya persistidos permanecen; el expediente incompleto
            # vuelve a catalogarse en el siguiente lote, sin saltarlo.
            checkpoints.record(store,dataset,partition,status="partial",count=len(output),error="inventory_incomplete")
            return {"status":"partial","dataset":dataset,"persisted_processes":len(output),
                    "cursor":completed,"processes":output,"error":"inventory_incomplete","national_coverage":False}
    return {"status":"ok","dataset":dataset,"persisted_processes":len(output),"cursor":completed,
            "processes":output,"end_of_current_sweep":len(rows)<limit,"national_coverage":False,
            "scope":"Descubrimiento de expedientes plurales; no atribucion de contratos al integrante"}
