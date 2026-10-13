"""Lote manual SECOP I/II reanudable. Se ejecuta separado de la web congelada."""
from __future__ import annotations

import re
from urllib.error import HTTPError

from index28.composition import norm
from index28.evidence import inspect_pdf
from index28.persistence import DocumentStore
from index28.expediente_secop_i import expediente as inventory_i
from index28.regimen_especial_secop2 import expediente as inventory_ii
from index28.document_worker import read_pdf_https,valid_document_uri
from index28.secop_i_documents import resolve_link,read_process,read_document,valid_pdf_url
from index28.socrata import fetch_json


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
        return str(exc) if str(exc) in {"invalid_link","invalid_pdf","reader_failed"} else "invalid_pdf"
    return "download_unavailable"


def run_process(store: DocumentStore, platform: str, reference: str, *, fetch=fetch_json,
                download_ii=read_pdf_https, html_i=read_process, download_i=read_document,
                parser=inspect_pdf, max_documents: int = 10, inventory: dict | None = None,
                use_ocr: bool = False) -> dict:
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
    document_by_key=dict(zip(keys,docs))
    # Lote cuenta intentos efectivos. Documentos leidos no consumen la cuota siguiente.
    attempted=0
    reused=0
    page=None
    page_error=None
    public_ref=snapshot.get("process_url") or "https://www.datos.gov.co/resource/dmgg-8hin.json?proceso="+reference
    for key in keys:
        if store.result(key) is not None:
            reused+=1
            continue
        if attempted>=max_documents:
            break
        job=store.claim(key,lease_seconds=300 if use_ocr else 180)
        if job is None:
            continue
        attempted+=1
        doc=document_by_key[key]
        url=doc.get("download_url_published")
        try:
            if platform=="SECOP II":
                if not url or not valid_document_uri(url):
                    raise ValueError("invalid_link")
                payload=download_ii(url)
            else:
                docid=job["document_id"]
                if not url or not valid_pdf_url(url,reference,docid):
                    if page is None and page_error is None:
                        try:
                            page=html_i(public_ref,reference)
                        except Exception as exc:
                            page_error=exc
                    if page_error is not None:
                        raise page_error
                    url=resolve_link(page,public_ref,reference,docid)
                if not url:
                    raise ValueError("invalid_link")
                payload=download_i(url,reference,docid)
            result=parser(payload,source=doc["source"],process_ref=reference,
                          process_url=public_ref,document_url=url,use_ocr=use_ocr)
            store.finish(key,job["lease_token"],result)
        except Exception as exc:
            code=error_code(exc)
            store.fail(key,job["lease_token"],error_code=code,
                       blocked=code in {"http_403","http_404","invalid_link","invalid_pdf"})
    states=store.queue_status(keys)
    complete=snapshot["complete_in_requested_sources"] and all(x["status"]=="parsed" for x in states)
    return {"platform":platform,"reference":reference,"inventory_key":snapshot_key,
            "documents_listed":len(docs),"attempted_in_batch":attempted,"previous_results_reused":reused,
            "jobs":states,"coverage":snapshot["coverage"],"complete_in_requested_sources":complete,
            "verified_member_contracts_created":0,"file_bytes_persisted":0,
            "remaining_documents":sum(x["status"]!="parsed" for x in states),
            "scope":"Lote documental experimental; requiere revision para atribucion contractual"}
