"""Catalogo FINDETER conectado a la cola, sin conservar archivos originales."""
from __future__ import annotations
import hashlib
import re
from urllib.parse import urlsplit,unquote,urljoin
from institutional_indexer import get_public
from index28.regimen_especial_secop2 import document_kind
from index28.pipeline import priority


def process_url(reference: str) -> str:
    if not re.fullmatch(r"PAF-[A-Z0-9-]{5,70}",reference):
        raise ValueError("Referencia FINDETER invalida")
    return "https://www.findeter.gov.co/convocatorias/"+reference.lower()


def valid_portal_document(url: str,reference: str) -> bool:
    try:
        u=urlsplit(str(url))
        return (u.scheme=="https" and u.hostname=="www.findeter.gov.co" and not u.username
                and not u.password and u.port in (None,443) and not u.query and not u.fragment
                and unquote(u.path).startswith("/system/files/convocatorias/"+reference+"/")
                and u.path.lower().endswith(".pdf") and ".." not in unquote(u.path).split("/"))
    except ValueError:return False


def read_portal_pdf(url: str,reference: str) -> bytes:
    if not valid_portal_document(url,reference):raise ValueError("invalid_link")
    from urllib.request import Request,build_opener,HTTPRedirectHandler
    class Redirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not valid_portal_document(newurl,reference) or unquote(urlsplit(newurl).path)!=unquote(urlsplit(url).path):
                raise ValueError("invalid_link")
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    with build_opener(Redirect()).open(Request(url,headers={"Accept":"application/pdf","User-Agent":"SECOP-Consulta-Mixta-Indexer/0.3"}),timeout=25) as stream:
        if not valid_portal_document(stream.geturl(),reference):raise ValueError("invalid_link")
        data=stream.read(15_000_001)
        if len(data)>15_000_000:raise ValueError("invalid_pdf")
    if not data.startswith(b"%PDF"):raise ValueError("invalid_pdf")
    return data


def catalogue_portal(store,reference: str,*,fetcher=get_public,use_ocr: bool=False) -> dict:
    url=process_url(reference);html,kind=fetcher(url,"findeter",max_bytes=2_000_000)
    if kind!="text/html":raise ValueError("El portal no devolvio una ficha HTML")
    from bs4 import BeautifulSoup
    page=BeautifulSoup(html,"html.parser")
    text=page.get_text(" ",strip=True)
    if reference not in text:raise ValueError("Ficha de otro expediente")
    # Conservar todos los PDF publicados dentro de este expediente. El nombre
    # puede ser "verificacion de requisitos habilitantes", no "evaluacion".
    observed={}
    for link in page.select("a[href]"):
        full=urljoin(url,str(link.get("href","")).strip())
        if not valid_portal_document(full,reference):continue
        row=link.find_parent("tr")
        label=(row.get_text(" ",strip=True) if row else link.get_text(" ",strip=True))[:450]
        observed[full]={"url":full,"label":label or unquote(urlsplit(full).path.rsplit("/",1)[-1])}
    accepted=sorted(observed.values(),key=lambda d:(priority({"description":d["label"],"kind":document_kind(d["label"])}),d["url"]))[:200]
    docs=[{"document_id":"FDT."+hashlib.sha256(d["url"].encode()).hexdigest()[:32],
           "filename":unquote(urlsplit(d["url"]).path.rsplit("/",1)[-1]),
           "description":d["label"],"source":"findeter_portal","kind":document_kind(d["label"]),
           "download_url_published":d["url"],"process_url":url,
           "reader_policy":"ocr_spa8_v211" if use_ocr else "text_v211"} for d in accepted]
    coverage={"source":"findeter_portal","status":"partial" if len(observed)>200 else "ok",
              "count":len(docs),"truncated":len(observed)>200,"scope":"Enlaces PDF visibles de esta ficha; no todo el portal"}
    snapshot={"platform":"FINDETER","reference":reference,"process_url":url,
              "document_metadata":docs,"contract_records":[],"coverage":[coverage],
              "complete_in_requested_sources":coverage["status"]=="ok"}
    store.create_document_schema();key=store.save_inventory(snapshot)
    jobs=[store.enqueue("FINDETER",reference,d,priority(d)) for d in docs]
    return {"platform":"FINDETER","reference":reference,"inventory_key":key,"job_keys":jobs,
            "documents_listed":len(docs),"coverage":[coverage],"national_coverage":False}
