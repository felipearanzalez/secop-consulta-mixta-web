"""Discover official SECOP I document metadata by exact process constancia.

No contract conclusions or downloadable document claims are drawn from metadata.
The API is read-only. This module NEVER downloads PDFs or follows legacy HTTP links.
It is intentionally separate from the live SECOP search and persistent index.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
import json
import re
from typing import Callable
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import Request, urlopen

BASE = "https://www.datos.gov.co/resource"
SECOP_PROCESS_URL = "https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia="
DATASETS = {
    "proponentes": {"id": "tauh-5jvn", "field": "id_proceso"},
    "archivos_actuales": {"id": "ps88-5e3v", "field": "numero_de_constancia"},
    "archivos_historicos": {"id": "8kpz-m6cc", "field": "numero_de_constancia"},
}
MAX_PAGES = 8
PAGE_SIZE = 250
KNOWN_DOWNLOAD_HOSTS = {"www.contratos.gov.co", "contratos.gov.co", "www.secop.gov.co", "www.datos.gov.co", "datos.gov.co"}
CONSTANCIA = re.compile(r"\d{2}-\d{1,2}-\d{1,14}\Z")
NIT = re.compile(r"\d{9}\Z")


@dataclass
class DocumentEntry:
    id: str
    process: str
    dataset: str
    filename: str
    document_type: str
    published_at: str
    official_process_url: str
    source_dataset_url: str
    verified_https_url: str | None
    download_status: str
    document_existence: str = "metadatos_publicados_sin_lectura_documental"


def valid_constancia(value: str) -> str:
    v = str(value or "").strip()
    if not CONSTANCIA.fullmatch(v):
        raise ValueError("Numero de constancia SECOP I invalido")
    return v


def process_url(constancia: str) -> str:
    return SECOP_PROCESS_URL + quote(valid_constancia(constancia), safe="-")


def field_url(dataset_id: str, field: str, constancia: str, limit: int, offset: int) -> str:
    if dataset_id not in {d["id"] for d in DATASETS.values()}:
        raise ValueError("Conjunto de datos no autorizado")
    if field not in {"id_proceso", "numero_de_constancia"}:
        raise ValueError("Campo no autorizado")
    value = valid_constancia(constancia)
    if not 1 <= limit <= 1000 or not 0 <= offset <= 100000:
        raise ValueError("Limites de paginacion invalidos")
    params = urlencode({"$where": f"{field}='{value}'", "$limit": limit, "$offset": offset})
    return f"{BASE}/{dataset_id}.json?{params}"


def official_https_url(raw: object) -> str | None:
    value = raw.get("url") if isinstance(raw, dict) else raw
    if not isinstance(value, str) or len(value) > 2000:
        return None
    try:
        u = urlsplit(value)
        if u.scheme == "https" and u.hostname in KNOWN_DOWNLOAD_HOSTS and u.username is None and u.password is None and u.port in (None, 443):
            return value
    except ValueError:
        pass
    return None


def default_json_fetch(url: str) -> list[dict]:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "www.datos.gov.co" or not parts.path.startswith("/resource/") or not parts.path.endswith(".json"):
        raise ValueError("Solo se permiten datos.gov.co/resource oficiales")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "SECOP-Consulta-Mixta-Auditoria/0.2"})
    with urlopen(req, timeout=18) as stream:
        body = stream.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("Respuesta excesiva")
    data = json.loads(body)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("Respuesta inesperada en Socrata")
    return data


def fetch_rows(name: str, constancia: str, fetch: Callable[[str], list[dict]] = default_json_fetch, page_size: int = PAGE_SIZE, max_pages: int = MAX_PAGES) -> tuple[list[dict], bool]:
    source = DATASETS[name]
    out: list[dict] = []
    truncated = False
    for page in range(max_pages):
        data = fetch(field_url(source["id"], source["field"], constancia, page_size, page * page_size))
        if not isinstance(data, list):
            raise ValueError("Respuesta de fuente no tabular")
        out.extend(data)
        if len(data) < page_size:
            return out, False
    # One extra row check distinguishes an exact full page from a truncated search.
    probe = fetch(field_url(source["id"], source["field"], constancia, 1, max_pages * page_size))
    truncated = bool(probe)
    return out, truncated


def document_type(row: dict) -> str:
    text = " ".join(str(row.get(key, "")) for key in ("descripcion", "palabras_clave", "nombrearchivo")).upper()
    if re.search(r"(CONFORMACI[ÓO]N|CONSORCIO|UNI[ÓO]N TEMPORAL|INTEGRANTES)", text):
        return "composicion_plural_posible"
    if re.search(r"(P[ÓO]LIZA|GARANT[IÍ]A)", text):
        return "garantias"
    if re.search(r"(EVALUACI[ÓO]N|INFORME FINAL|RESULTADO FINAL)", text):
        return "evaluacion"
    if re.search(r"(ADJUDICACI[ÓO]N|RESOLUCION DE ADJUDICACION)", text):
        return "adjudicacion"
    if re.search(r"(CONTRATO|MINUTA)", text):
        return "contrato_posible"
    if re.search(r"(ACTA DE INICIO|ACTA DE REINICIO|SUSPENSI[ÓO]N)", text):
        return "ejecucion_posible"
    return "otro"


def normal_proponent_nit(value: object) -> str | None:
    """Never infer NIT from bidder's name or use 'No Definido' as identification."""
    text = str(value or "").strip()
    parts = text.split("-", maxsplit=1)
    cleaned = re.sub(r"[ .]", "", parts[0])
    return cleaned if NIT.fullmatch(cleaned) else None


def inventory(constancia: str, fetch: Callable[[str], list[dict]] = default_json_fetch) -> dict:
    """Build one non-attributive process inventory. Any failed source stays explicitly incomplete."""
    c = valid_constancia(constancia)
    docs: OrderedDict[str, DocumentEntry] = OrderedDict()
    proponents: list[dict] = []
    coverage: list[dict] = []
    for source in ("archivos_actuales", "archivos_historicos", "proponentes"):
        ds = DATASETS[source]
        try:
            rows, truncated = fetch_rows(source, c, fetch=fetch)
            coverage.append({"source": ds["id"], "records": len(rows), "state": "partial" if truncated else "ok", "truncated": truncated})
            if source == "proponentes":
                for r in rows:
                    proponents.append({
                        "name": str(r.get("proponente") or ""),
                        "nit": normal_proponent_nit(r.get("num_doc_proponente")),
                        "awarded_in_dataset": str(r.get("adjudicado") or "").upper() in {"SI", "SÍ", "TRUE", "YES", "1"},
                        "contract_number_reported": str(r.get("numero_contrato") or ""),
                        "proof_level": "registro_de_proponente_no_equivale_a_contrato_firmado",
                    })
            else:
                for r in rows:
                    key = str(r.get("identificador") or "").strip()
                    if not key:
                        continue
                    safe = official_https_url(r.get("ruta_descarga"))
                    document = DocumentEntry(
                        id=key, process=c, dataset=ds["id"], filename=str(r.get("nombrearchivo") or ""),
                        document_type=document_type(r), published_at=str(r.get("fecha_ultima_modificacion") or r.get("fecha_creacion") or ""),
                        official_process_url=process_url(c), source_dataset_url=f"https://www.datos.gov.co/d/{ds['id']}",
                        verified_https_url=safe,
                        download_status="enlace_https_aceptable_pendiente_de_verificacion" if safe else "enlace_de_descarga_no_validado_o_inseguro",
                    )
                    if key not in docs or (source == "archivos_actuales" and docs[key].dataset != ds["id"]):
                        docs[key] = document
        except Exception as exc:
            coverage.append({"source": ds["id"], "records": None, "state": "failed", "error": str(exc)[:160]})
    return {
        "process": c,
        "official_process_url": process_url(c),
        "documents": [asdict(v) for v in docs.values()],
        "proponents": proponents,
        "coverage": coverage,
        "document_read_count": 0,
        "document_bytes_persisted": 0,
        "contracts_proven_by_metadata_only": 0,
        "requested_sources_returned_without_error": all(e["state"] == "ok" for e in coverage),
        "national_coverage": "no_acreditada",
    }
