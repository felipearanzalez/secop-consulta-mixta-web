"""Expediente SECOP I: fusion no atributiva de contratos y metadatos de archivos.

El informe no presume que un NIT mencionado en un archivo sea integrante de un
consorcio ni que el estado publicado demuestre ejecucion actual.
"""
from __future__ import annotations

from typing import Callable
from index28.socrata import scan_exact, fetch_json, VALID_CONSTANCIA

DATASETS = ("f789-7hwg", "qddk-cgux", "tauh-5jvn", "ps88-5e3v", "8kpz-m6cc")


def _real(value) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in {"no definido", "no definida", "none", "null", "n/a"} else text


def _contract(row: dict, dataset: str) -> dict:
    reference = _real(row.get("numero_de_constancia"))
    number = _real(row.get("numero_del_contrato")) or _real(row.get("numero_de_contrato"))
    signed = _real(row.get("fecha_de_firma_del_contrato"))
    name = _real(row.get("nom_razon_social_contratista")) or _real(row.get("nom_raz_social_contratista"))
    return {
        "record_id": _real(row.get("uid")) or dataset + ":" + reference + ":" + number,
        "constancia": reference,
        "number": number,
        "contractor": name,
        "contractor_nit_reported": _real(row.get("identificacion_del_contratista")),
        "entity": _real(row.get("nombre_entidad")) or _real(row.get("nombre_de_la_entidad")),
        "signature_date_reported": signed,
        "start_date_reported": _real(row.get("fecha_ini_ejec_contrato")),
        "end_date_reported": _real(row.get("fecha_fin_ejec_contrato")),
        "state_reported": _real(row.get("estado_del_proceso")),
        "value_reported": _real(row.get("valor_contrato_con_adiciones")) or _real(row.get("cuantia_contrato")),
        "source": dataset,
        "evidence_status": "registro_estructurado_sin_examen_del_contrato",
        "contract_signature_recorded": bool(signed),
    }


def expediente(constancia: str, fetch: Callable[[str], list[dict]] = fetch_json,
               page_size: int = 200, max_pages: int = 5) -> dict:
    if not VALID_CONSTANCIA.fullmatch(str(constancia)):
        raise ValueError("Constancia SECOP I invalida")
    results: dict[str, list[dict]] = {}
    coverage: list[dict] = []
    for ds in DATASETS:
        data, scan = scan_exact(ds, constancia, fetch=fetch, page_size=page_size, max_pages=max_pages)
        # Never trust a fixture or source response that does not match the reference.
        field = "id_proceso" if ds == "tauh-5jvn" else "numero_de_constancia"
        matched = [row for row in data if str(row.get(field)) == constancia]
        if len(matched) != len(data):
            scan["status"] = "partial"
            scan["error"] = "La fuente devolvio registros con otra constancia"
        results[ds] = matched
        coverage.append(scan)
    records = []
    seen = set()
    for ds in ("f789-7hwg", "qddk-cgux"):
        for row in results[ds]:
            item = _contract(row, ds)
            key = item["record_id"]
            if key in seen:
                continue
            seen.add(key)
            records.append(item)
    names: list[dict] = []
    for p in results["tauh-5jvn"]:
        names.append({"name": _real(p.get("proponente")),
                      "document_reported": _real(p.get("num_doc_proponente")),
                      "awarded_reported": _real(p.get("adjudicado")),
                      "number_reported": _real(p.get("numero_contrato")),
                      "evidence_status": "proponente_registrado_no_acredita_firma"})
    docs = []
    ids = set()
    for ds in ("ps88-5e3v", "8kpz-m6cc"):
        for row in results[ds]:
            ident = _real(row.get("identificador"))
            if not ident or ident in ids:
                continue
            ids.add(ident)
            docs.append({"id": ident, "name": _real(row.get("nombrearchivo")),
                         "description": _real(row.get("descripcion")),
                         "created_at": _real(row.get("fecha_creacion")),
                         "modified_at": _real(row.get("fecha_ultima_modificacion")),
                         "source": ds, "evidence_status": "metadatos_sin_lectura",
                         "source_url": f"https://www.datos.gov.co/d/{ds}",
                         "safe_public_download_verified": False})
    return {
        "platform": "SECOP I", "reference": constancia,
        "process_url": f"https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia={constancia}",
        "contract_records": records, "proponent_records": names, "document_metadata": docs,
        "coverage": coverage, "complete_in_requested_sources": all(x["status"] == "ok" for x in coverage),
        "document_texts_examined": 0, "membership_confirmed_by_documents": 0,
        "scope": "Inventario de fuentes, no certificacion de contratos ni busqueda nacional exhaustiva"
    }
