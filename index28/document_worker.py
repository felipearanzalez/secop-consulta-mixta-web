"""Procesamiento controlado de PDF SECOP II: solo indicios, nunca contratos.

Permite inyectar un descargador en pruebas. El descargador real restringe
redirecciones y contenido al dominio/ruta oficiales previamente publicados.
Los PDF se procesan en memoria y no se almacenan en PostgreSQL.
"""
from __future__ import annotations

from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from typing import Callable

from index28.evidence import parse_pdf, MAX_DOCUMENT_BYTES
from index28.regimen_especial_secop2 import expediente, DOCS
from index28.socrata import fetch_json
from index27.store import Store

PRIORITY = {"contrato_posible": 0, "posible_composicion": 1, "garantia": 2,
            "evaluacion": 3, "adjudicacion": 4, "suspension": 5,
            "modificacion": 6, "inicio": 7}


def valid_document_uri(raw: str) -> bool:
    try:
        parsed = urlsplit(str(raw))
        parts = parse_qs(parsed.query, keep_blank_values=True)
        return (parsed.scheme == "https" and parsed.hostname == "community.secop.gov.co"
                and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
                and parsed.path.rstrip("/") == "/Public/Archive/RetrieveFile/Index"
                and len(parts.get("DocumentId", [])) == 1 and parts["DocumentId"][0].isdigit())
    except ValueError:
        return False


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not valid_document_uri(newurl):
            raise ValueError("Redireccion de documento fuera del dominio/ruta autorizados")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_pdf_https(url: str) -> bytes:
    if not valid_document_uri(url):
        raise ValueError("Enlace documental no autorizado")
    request = Request(url,headers={"Accept":"application/pdf,application/octet-stream", "User-Agent":"SECOP-Consulta-Mixta-Indexer/0.3"})
    with build_opener(SafeRedirect()).open(request,timeout=20) as res:
        if not valid_document_uri(res.geturl()):
            raise ValueError("Enlace de respuesta no autorizado")
        content_type = res.headers.get_content_type()
        if content_type not in {"application/pdf", "application/octet-stream"}:
            raise ValueError("Respuesta no corresponde a PDF publico (tipo "+content_type+")")
        reported = res.headers.get("Content-Length", "")
        if reported.isdecimal() and int(reported)>MAX_DOCUMENT_BYTES:
            raise ValueError("PDF excede limite de tamano")
        payload = res.read(MAX_DOCUMENT_BYTES+1)
    if len(payload)>MAX_DOCUMENT_BYTES or not payload.startswith(b"%PDF"):
        raise ValueError("PDF ausente o tamano no permitido")
    return payload


def inspect_portfolio(portfolio: str, *, fetch: Callable[[str], list[dict]] = fetch_json,
                      download: Callable[[str], bytes] = read_pdf_https,
                      max_documents: int = 3, store: Store | None = None) -> dict:
    if not 1 <= max_documents <= 10:
        raise ValueError("Limite de documentos debe estar entre 1 y 10")
    original = expediente(portfolio,fetch=fetch)
    selection = sorted((x for x in original["document_metadata"] if x["kind"] in PRIORITY),
                       key=lambda x:(PRIORITY[x["kind"]], x["document_id"]))[:max_documents]
    inspected=[]
    observed=0
    # The source listing is a valid official reference if the process notice cannot be resolved.
    public_reference = "https://www.datos.gov.co/resource/"+DOCS+".json?proceso="+portfolio
    for doc in selection:
        url=doc.get("download_url_published")
        state={"document_id":doc["document_id"],"filename":doc["filename"],
               "kind":doc["kind"],"url":url,"status":"not_read", "indicators":0,
               "document_preserved":False,"member_verified":False,"contract_verified":False}
        try:
            if not url or not valid_document_uri(url):
                state["status"]="link_not_validated"
                inspected.append(state)
                continue
            parsed = parse_pdf(download(url), source=DOCS,process_ref=portfolio,
                               process_url=public_reference,document_url=url)
            incomplete=bool(parsed.get("truncated") or parsed.get("unreadable_pages") or parsed.get("errors"))
            state["status"]="partial" if incomplete else "parsed"
            state["indicators"]=len(parsed["indicators"])
            state["sha256"]=parsed["sha256"];state["pages_examined"]=parsed["pages_examined"]
            state["pages_reported"]=parsed["pages_reported"]
            state["unreadable_pages"]=parsed.get("unreadable_pages",[])
            observed+=state["indicators"]
            if store:
                for hint in parsed["indicators"]:
                    store.upsert_indicator(hint)
        except Exception as exc:
            state["status"]="failed";state["error"]=str(exc)[:200]
        inspected.append(state)
    return {"portfolio":portfolio,"documents_available":len(original["document_metadata"]),
            "documents_selected":len(selection),"documents_inspected":inspected,
            "indicators_detected":observed,
            "membership_confirmed":0,"contract_proven_from_document":0,
            "file_bytes_persisted":0,
            "coverage":original["coverage"],
            "coverage_complete":original["complete_in_requested_sources"] and all(x["status"]=="parsed" for x in inspected),
            "note":"No se atribuye un contrato por la sola presencia de NIT en un documento"}
