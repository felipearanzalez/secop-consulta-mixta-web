"""Enlaces SECOP I publicados en la ficha oficial; nunca inventa una ruta de archivo."""
from __future__ import annotations
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit,urljoin,unquote,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler

from index28.socrata import VALID_CONSTANCIA
from index28.evidence import MAX_DOCUMENT_BYTES

HOSTS = {"www.contratos.gov.co","contratos.gov.co"}


def valid_process_url(url: str, reference: str) -> bool:
    try:
        u=urlsplit(url)
        return (bool(VALID_CONSTANCIA.fullmatch(reference)) and u.scheme=="https" and u.hostname in HOSTS
                and u.username is None and u.password is None and u.port in (None,443)
                and u.path=="/consultas/detalleProceso.do"
                and parse_qs(u.query).get("numConstancia")==[reference])
    except ValueError:
        return False


def valid_pdf_url(url: str, reference: str, document_id: str) -> bool:
    try:
        u=urlsplit(url)
        path=unquote(u.path)
        return (bool(VALID_CONSTANCIA.fullmatch(reference)) and document_id.isdecimal()
                and len(document_id)<=14 and u.scheme=="https" and u.hostname in HOSTS
                and u.username is None and u.password is None and u.port in (None,443)
                and not u.query and not u.fragment and ".." not in path.split("/")
                and path.lower().endswith(".pdf") and reference in path
                and bool(re.search(r"(?:^|[/_\-])"+re.escape(document_id)+r"(?:[_\-.]|$)",path)))
    except ValueError:
        return False


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls=[]
    def handle_starttag(self, tag, attrs):
        if tag=="a":
            href=dict(attrs).get("href")
            if href:
                self.urls.append(href)


def resolve_link(html: bytes, process_url: str, reference: str, document_id: str) -> str | None:
    if not valid_process_url(process_url,reference) or len(html)>2_000_000:
        raise ValueError("Ficha de expediente invalida")
    parser=_Links()
    parser.feed(html.decode("utf-8",errors="replace"))
    links=list(dict.fromkeys(urljoin(process_url,href) for href in parser.urls))
    matches=[u for u in links if valid_pdf_url(u,reference,document_id)]
    # Enlaces ambiguos permanecen sin resolver hasta revisar su identidad.
    return matches[0] if len(matches)==1 else None


def _read(url: str, validator, maximum: int, types: set[str]) -> bytes:
    if not validator(url):
        raise ValueError("invalid_link")
    class Redirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not validator(newurl):
                raise ValueError("invalid_link")
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    request=Request(url,headers={"User-Agent":"SECOP-Consulta-Mixta-Indexer/0.4",
                                "Accept":",".join(sorted(types))})
    with build_opener(Redirect()).open(request,timeout=18) as response:
        if not validator(response.geturl()) or response.headers.get_content_type() not in types:
            raise ValueError("invalid_link")
        size=response.headers.get("Content-Length","")
        if size.isdecimal() and int(size)>maximum:
            raise ValueError("Respuesta demasiado grande")
        payload=response.read(maximum+1)
    if len(payload)>maximum:
        raise ValueError("Respuesta demasiado grande")
    return payload


def read_process(url: str, reference: str) -> bytes:
    return _read(url,lambda u:valid_process_url(u,reference),2_000_000,{"text/html"})


def read_document(url: str, reference: str, document_id: str) -> bytes:
    payload=_read(url,lambda u:valid_pdf_url(u,reference,document_id),MAX_DOCUMENT_BYTES,
                  {"application/pdf","application/octet-stream"})
    if not payload.startswith(b"%PDF"):
        raise ValueError("invalid_pdf")
    return payload
