"""Lote manual SECOP I/II reanudable. Se ejecuta separado de la web congelada."""
from __future__ import annotations

import re
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs,urlsplit

from index28.composition import norm
from index28.evidence import inspect_pdf
from index28.persistence import DocumentStore
from index28.expediente_secop_i import expediente as inventory_i
from index28.regimen_especial_secop2 import expediente as inventory_ii
from index28.document_worker import read_pdf_https,valid_document_uri
from index28.secop_i_documents import resolve_link,read_process,read_document,valid_pdf_url
from index28.socrata import fetch_json
from index28.reading_progress import retryable_pages


def priority(doc: dict) -> int:
    text=norm(" ".join(str(doc.get(k) or "") for k in ("name","filename","description","kind")))
    # Orden acordado para identificar integrantes: informes y polizas primero.
    if re.search(r"EVALUAC|POLIZA|GARANTIA|GARANT[IÍ]AS",text):
        return 0
    if re.search(r"CONFORMAC|CONSORCIO|UNION TEMPORAL|COMPOSICION",text):
        return 1
    if re.search(r"CONTRATO|ADJUDICACION",text):
        return 2
    if re.search(r"INICIO|SUSPENSION|OTROSI|PRORROGA|MODIFICACION|LIQUIDACION",text):
        return 3
    return 4


def error_code(exc: Exception) -> str:
    if isinstance(exc,HTTPError):
        return {403:"http_403",404:"http_404",429:"http_429"}.get(exc.code,"http_error")
    if isinstance(exc,ValueError):
        return str(exc) if str(exc) in {"invalid_link","invalid_pdf","reader_failed","document_changed"} else "invalid_pdf"
    return "download_unavailable"


def execute_job(store: DocumentStore,key: str,*,download_ii=read_pdf_https,
                html_i=read_process,download_i=read_document,parser=inspect_pdf,
                use_ocr: bool=False,max_pages: int=8) -> dict:
    """Procesar o reanudar un trabajo ya existente, sin reinventariar su expediente."""
    if not isinstance(use_ocr,bool) or not 1<=max_pages<=8:
        raise ValueError("Limites del lector invalidos")
    job=store.job(key)
    previous=store.result(key)
    pending=retryable_pages(previous,max_pages) if previous else None
    if previous and not pending:
        return {"job_key":key,"attempted":False,"reused":True,"status":job["status"]}
    platform=job["platform"];reference=job["process_ref"]
    block=store.source_block(platform,reference)
    if block:
        return {"job_key":key,"attempted":False,"reused":False,"status":"source_deferred",
                "error_code":block["error_code"],"next_retry":block["next_retry"]}
    claimed=store.claim(key,lease_seconds=330 if use_ocr else 180,
                        max_attempts=10 if previous else 3,resume_partial=bool(previous))
    if claimed is None:
        return {"job_key":key,"attempted":False,"reused":False,"status":job["status"]}
    doc=claimed["document"]
    url=doc.get("download_url_published")
    public_ref=("https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia="+reference
                if platform=="SECOP I" else "https://www.datos.gov.co/resource/dmgg-8hin.json?proceso="+reference)
    try:
        if platform=="SECOP II":
            if not url or not valid_document_uri(url) or parse_qs(urlsplit(url).query).get("DocumentId")!=[job["document_id"]]:
                raise ValueError("invalid_link")
            payload=download_ii(url)
        else:
            if not url or not valid_pdf_url(url,reference,job["document_id"]):
                page=html_i(public_ref,reference)
                url=resolve_link(page,public_ref,reference,job["document_id"])
            if not url:
                raise ValueError("invalid_link")
            payload=download_i(url,reference,job["document_id"])
        context={"source":doc["source"],"process_ref":reference,"process_url":public_ref,
                 "document_url":url,"use_ocr":use_ocr,"max_pages":max_pages}
        if previous:
            context.update(selected_pages=pending,resume_sha256=previous["sha256"])
        current=parser(payload,**context)
        store.finish(key,claimed["lease_token"],current)
        merged=store.result(key)
        return {"job_key":key,"attempted":True,"reused":False,"status":store.job(key)["status"],
                "pages_selected":current.get("selected_pages"),"pages_read":merged.get("pages_read",0),
                "pending_pages":merged.get("pending_pages",[]),"sha256":merged["sha256"]}
    except Exception as exc:
        code=error_code(exc)
        store.fail(key,claimed["lease_token"],error_code=code,
                   blocked=code in {"http_403","http_404","invalid_link","invalid_pdf","document_changed"})
        if code=="http_403":
            store.defer_source(platform,reference,code)
        return {"job_key":key,"attempted":True,"reused":False,"status":store.job(key)["status"],"error_code":code}


def run_process(store: DocumentStore, platform: str, reference: str, *, fetch=fetch_json,
                download_ii=read_pdf_https, html_i=read_process, download_i=read_document,
                parser=inspect_pdf, max_documents: int = 10, inventory: dict | None = None,
                use_ocr: bool = False,max_pages_per_document: int=8) -> dict:
    if not 1 <= max_documents <= 50 or platform not in {"SECOP I","SECOP II"}:
        raise ValueError("Limite de lote o plataforma invalida")
    snapshot=inventory if inventory is not None else (
        inventory_i(reference,fetch=fetch) if platform=="SECOP I" else inventory_ii(reference,fetch=fetch))
    if snapshot["platform"]!=platform or (snapshot.get("reference") or snapshot.get("portfolio"))!=reference:
        raise ValueError("Inventario de otro expediente")
    store.create_document_schema()
    snapshot_key=store.save_inventory(snapshot)
    if not isinstance(use_ocr,bool):
        raise ValueError("Opcion OCR invalida")
    docs=[{**d,"reader_policy":"ocr_spa8_v211" if use_ocr else "text_v211"} for d in snapshot["document_metadata"]]
    docs=sorted(docs,key=lambda d:(priority(d),str(d.get("id") or d.get("document_id"))))
    keys=[store.enqueue(platform,reference,doc,priority(doc)) for doc in docs]
    # Lote cuenta intentos efectivos. Documentos leidos no consumen la cuota siguiente.
    attempted=0
    reused=0
    outcomes=[]
    for key in keys:
        if attempted>=max_documents:
            break
        response=execute_job(store,key,download_ii=download_ii,html_i=html_i,download_i=download_i,
                             parser=parser,use_ocr=use_ocr,max_pages=max_pages_per_document)
        outcomes.append(response)
        attempted+=int(response["attempted"])
        reused+=int(response["reused"])
    states=store.queue_status(keys)
    complete=snapshot["complete_in_requested_sources"] and all(x["status"]=="parsed" for x in states)
    return {"platform":platform,"reference":reference,"inventory_key":snapshot_key,
            "documents_listed":len(docs),"attempted_in_batch":attempted,"previous_results_reused":reused,
            "jobs":states,"batch_outcomes":outcomes,"coverage":snapshot["coverage"],"complete_in_requested_sources":complete,
            "verified_member_contracts_created":0,"file_bytes_persisted":0,
            "remaining_documents":sum(x["status"]!="parsed" for x in states),
            "scope":"Lote documental experimental; requiere revision para atribucion contractual"}


def catalogue_process(store: DocumentStore,platform: str,reference: str,*,fetch=fetch_json,use_ocr: bool=False) -> dict:
    """Catalogacion sin lectura, para alimentar una cola independiente del NIT consultado."""
    if platform not in {"SECOP I","SECOP II"}:
        raise ValueError("Plataforma invalida")
    snapshot=inventory_i(reference,fetch=fetch) if platform=="SECOP I" else inventory_ii(reference,fetch=fetch)
    store.create_document_schema()
    inventory_key=store.save_inventory(snapshot)
    docs=sorted(snapshot["document_metadata"],key=lambda d:(priority(d),str(d.get("id") or d.get("document_id"))))
    keys=[store.enqueue(platform,reference,{**doc,"reader_policy":"ocr_spa8_v211" if use_ocr else "text_v211"},priority(doc)) for doc in docs]
    return {"platform":platform,"reference":reference,"inventory_key":inventory_key,"job_keys":keys,
            "documents_listed":len(docs),"coverage":snapshot["coverage"],
            "catalogue_complete":snapshot["complete_in_requested_sources"],"documents_read":0,
            "verified_member_contracts_created":0}


def work_queue(store: DocumentStore,*,max_documents: int=20,max_pages_per_document: int=3,
               max_seconds: int=300,use_ocr: bool=False,on_progress=None,job_keys: list[str] | None=None,**adapters) -> dict:
    """Drenaje manual acotado. No crea procesos programados ni servicios en nube."""
    if not 1<=max_documents<=100 or not 10<=max_seconds<=900:
        raise ValueError("Cuota de trabajo invalida")
    store.create_document_schema()
    start=time.monotonic();out=[]
    keys=store.ready_jobs(max_documents) if job_keys is None else job_keys[:max_documents]
    if job_keys is not None and (len(job_keys)>100 or any(not re.fullmatch(r"[a-f0-9]{64}",key) for key in job_keys)):
        raise ValueError("Lista de trabajos invalida")
    for key in keys:
        if time.monotonic()-start>=max_seconds:
            break
        result=execute_job(store,key,use_ocr=use_ocr,max_pages=max_pages_per_document,**adapters)
        out.append(result)
        if on_progress:
            on_progress(result)
    return {"attempted_in_batch":sum(int(r["attempted"]) for r in out),"results":out,
            "elapsed_seconds":round(time.monotonic()-start,2),"overview":store.overview(),
            "verified_member_contracts_created":0,"file_bytes_persisted":0,
            "scope":"Procesamiento de la cola experimental, sin atribucion contractual automatica"}
