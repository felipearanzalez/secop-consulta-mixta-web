"""Inventario SECOP II para investigar expedientes publicados, especialmente regimen especial.

Los metadatos de archivos no constituyen prueba de firma, adjudicacion ni
composicion plural. Documentos y contratos estructurados se reportan aparte.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, parse_qs
from typing import Callable

from index28.socrata import VALID_PORTFOLIO, scan_exact, fetch_json

DOCS = "dmgg-8hin"
CONTRACTS = "jbjy-vk9h"
PROCESSES = "p6dx-8zbt"
PCCNTR = re.compile(r"CO1\.PCCNTR\.\d{3,}\Z")
ID = re.compile(r"\d{3,14}\Z")


def _norm(v: object) -> str:
    text = unicodedata.normalize("NFKD", str(v or "").upper())
    return "".join(c for c in text if not unicodedata.combining(c))


def special_modality(v: object) -> bool:
    norm = _norm(v)
    return "REGIMEN ESPECIAL" in norm


def document_kind(filename: object) -> str:
    name = _norm(filename)
    if re.search(r"CONFORMACION|CONSORCIO|UNION TEMPORAL|INTEGRANTES|PARTICIPACION", name):
        return "posible_composicion"
    if re.search(r"POLIZA|GARANTIA", name):
        return "garantia"
    if re.search(r"INFORME.*EVALUACION|EVALUACION|INFORME FINAL", name):
        return "evaluacion"
    if re.search(r"ADJUDICACION|RESOLUCION DE ADJUDICACION", name):
        return "adjudicacion"
    if re.search(r"ACTA DE INICIO|ACTA INICIO", name):
        return "inicio"
    if re.search(r"SUSPENSION|ACTA DE SUSPENSION", name):
        return "suspension"
    if re.search(r"MODIFICACION|OTROSI|PRORROGA|ADICION", name):
        return "modificacion"
    if re.search(r"\bCONTRATO\b|MINUTA", name):
        return "contrato_posible"
    return "otro"


def published_document_link(row: dict) -> str | None:
    doc_id = str(row.get("id_documento") or "").strip()
    if not ID.fullmatch(doc_id):
        return None
    raw = row.get("url_descarga_documento")
    if isinstance(raw, dict):
        raw = raw.get("url")
    if not isinstance(raw, str) or len(raw) > 2000:
        return None
    try:
        uri = urlsplit(raw)
        if uri.scheme != "https" or uri.hostname != "community.secop.gov.co" or uri.username is not None or uri.password is not None or uri.port not in (None, 443):
            return None
        if uri.path.rstrip("/") != "/Public/Archive/RetrieveFile/Index":
            return None
        params = parse_qs(uri.query, keep_blank_values=True)
        if params.get("DocumentId") != [doc_id]:
            return None
        return raw
    except ValueError:
        return None


def expediente(portfolio: str, fetch: Callable[[str], list[dict]] = fetch_json,
               page_size: int = 200, max_pages: int = 5) -> dict:
    if not VALID_PORTFOLIO.fullmatch(str(portfolio)):
        raise ValueError("Codigo de portafolio SECOP II invalido")
    coverage: list[dict] = []
    data: dict[str, list[dict]] = {}
    field = {CONTRACTS: "proceso_de_compra", PROCESSES: "id_del_portafolio", DOCS: "proceso"}
    for ds in (CONTRACTS, PROCESSES, DOCS):
        records, status = scan_exact(ds, portfolio, fetch=fetch, page_size=page_size, max_pages=max_pages)
        accepted = [r for r in records if str(r.get(field[ds])) == portfolio]
        if len(accepted) != len(records):
            status["status"] = "partial"
            status["error"] = "Referencia ajena a la solicitud devuelta por la fuente"
        data[ds] = accepted
        coverage.append(status)
    contracts = []
    for row in data[CONTRACTS]:
        number = str(row.get("id_contrato") or "").strip()
        if not PCCNTR.fullmatch(number):
            continue
        state = str(row.get("estado_contrato") or "").strip()
        if any(text in _norm(state) for text in ("BORRADOR", "EN APROBACION", "EN FIRMA", "PENDIENTE DE FIRMA")):
            continue
        contracts.append({
            "contract_id": number, "contract_reference": str(row.get("referencia_del_contrato") or ""),
            "contractor": str(row.get("proveedor_adjudicado") or ""),
            "contractor_document": str(row.get("documento_proveedor") or ""),
            "provider_code": str(row.get("codigo_proveedor") or ""),
            "entity": str(row.get("nombre_entidad") or ""),
            "status_reported": state,
            "signature_date_reported": str(row.get("fecha_de_firma") or ""),
            "start_date_reported": str(row.get("fecha_de_inicio_de_ejecucion") or row.get("fecha_de_inicio_del_contrato") or ""),
            "end_date_reported": str(row.get("fecha_de_fin_de_ejecucion") or row.get("fecha_de_fin_del_contrato") or ""),
            "value_reported": str(row.get("valor_del_contrato") or ""),
            "special_modality_reported": special_modality(row.get("modalidad_de_contratacion")),
            "source": CONTRACTS,
            "evidence_status": "registro_contractual_publicado_sin_lectura_del_contrato",
            "official_url": f"https://community.secop.gov.co/Public/Tendering/ContractDetailView/Index?UniqueIdentifier={number}",
        })
    processes = []
    for row in data[PROCESSES]:
        processes.append({
            "process_id": str(row.get("id_del_proceso") or ""),
            "reference": str(row.get("referencia_del_proceso") or ""),
            "entity": str(row.get("entidad") or ""),
            "modality": str(row.get("modalidad_de_contratacion") or ""),
            "special_modality_reported": special_modality(row.get("modalidad_de_contratacion")),
            "awarded_reported": str(row.get("adjudicado") or ""),
            "source": PROCESSES, "evidence_status": "publicacion_del_proceso_no_prueba_contrato",
        })
    documents = []
    seen_ids = set()
    for row in data[DOCS]:
        document_id = str(row.get("id_documento") or "").strip()
        if not ID.fullmatch(document_id) or document_id in seen_ids:
            continue
        seen_ids.add(document_id)
        filename = str(row.get("nombre_archivo") or "")[:450]
        documents.append({
            "document_id": document_id, "filename": filename,
            "kind": document_kind(" ".join([filename, str(row.get("descripci_n") or "")])),
            "entity": str(row.get("entidad") or ""),
            "loaded_at": str(row.get("fecha_carga") or ""),
            "reported_contract_number": str(row.get("n_mero_de_contrato") or ""),
            "download_url_published": published_document_link(row),
            "access_confirmed": False,
            "source": DOCS, "evidence_status": "metadatos_de_archivo_sin_lectura",
        })
    special = any(x["special_modality_reported"] for x in contracts + processes)
    return {
        "platform": "SECOP II", "portfolio": portfolio,
        "is_special_regime_reported": special,
        "regime_classification": "regimen_especial_reportado" if special else "regimen_no_confirmado_en_fuentes_estructuradas",
        "contract_records": contracts, "process_records": processes,
        "document_metadata": documents,
        "coverage": coverage,
        "complete_in_requested_sources": all(x["status"] == "ok" for x in coverage),
        "document_texts_examined": 0,
        "member_contract_relations_verified": 0,
        "scope": "Inventario experimental, no prueba de contrato suscrito ni ejecucion material",
    }
