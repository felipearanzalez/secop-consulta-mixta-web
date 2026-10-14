"""Descubrir regimen especial sin exigir NIT o adjudicatario en datos estructurados."""
from urllib.parse import urlencode
from index28.socrata import BASE,fetch_json,VALID_PORTFOLIO
from index28.regimen_especial_secop2 import expediente
from index28 import checkpoints
from index28.pipeline import priority


def discovery_url(cursor: str="",limit: int=3) -> str:
    if not 1<=limit<=20 or cursor and not VALID_PORTFOLIO.fullmatch(cursor):raise ValueError("Cursor o limite invalido")
    where="id_del_portafolio IS NOT NULL AND (upper(modalidad_de_contratacion) like '%RÉGIMEN ESPECIAL%' OR upper(modalidad_de_contratacion) like '%REGIMEN ESPECIAL%')"
    if cursor:where+=" AND id_del_portafolio > '"+cursor+"'"
    return BASE+"/p6dx-8zbt.json?"+urlencode({"$select":"id_del_portafolio","$group":"id_del_portafolio","$where":where,"$order":"id_del_portafolio ASC","$limit":limit})


def seed_special(store,*,partition: str="special_initial",limit: int=3,fetch=fetch_json,inventory_fn=expediente,use_ocr: bool=False) -> dict:
    store.create_document_schema();checkpoints.ensure_schema(store)
    prior=checkpoints.read(store,"p6dx-8zbt",partition) or {};cursor=prior.get("cursor","");completed=cursor;out=[]
    try:
        rows=fetch(discovery_url(cursor,limit))
        ids=[str(r.get("id_del_portafolio") or "") for r in rows]
        if len(rows)>limit or any(not VALID_PORTFOLIO.fullmatch(x) or cursor and x<=cursor for x in ids) or ids!=sorted(set(ids)):
            raise ValueError("Orden de descubrimiento invalido")
    except Exception:
        checkpoints.record(store,"p6dx-8zbt",partition,status="failed",count=0,error="special_discovery_failed")
        return {"status":"failed","cursor":cursor,"persisted_processes":0,"error":"special_discovery_failed","national_coverage":False}
    for reference in ids:
        try:
            snapshot=inventory_fn(reference,fetch=fetch)
            if snapshot.get("platform")!="SECOP II" or snapshot.get("portfolio")!=reference:raise ValueError("Otro expediente")
            key=store.save_inventory(snapshot)
            jobs=[store.enqueue("SECOP II",reference,{**d,"reader_policy":"ocr_spa8_v211" if use_ocr else "text_v211"},priority(d)) for d in snapshot["document_metadata"]]
            if not snapshot["complete_in_requested_sources"]:raise ValueError("Inventario parcial")
            out.append({"portfolio":reference,"inventory_key":key,"documents_queued":len(jobs),"structured_contracts":len(snapshot["contract_records"])})
            completed=reference;checkpoints.record(store,"p6dx-8zbt",partition,status="ok",count=len(out),cursor=completed)
        except Exception:
            checkpoints.record(store,"p6dx-8zbt",partition,status="partial",count=len(out),error="special_inventory_incomplete")
            return {"status":"partial","cursor":completed,"persisted_processes":len(out),"processes":out,"national_coverage":False}
    return {"status":"ok","cursor":completed,"persisted_processes":len(out),"processes":out,
            "end_of_current_sweep":len(ids)<limit,"national_coverage":False,
            "scope":"Barrido manual del catalogo de regimen especial; no certifica ausencia de contratos"}
