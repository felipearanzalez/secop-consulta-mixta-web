"""Lectura temporal, acotada y NO atributiva de un PDF publico.

Solo devuelve menciones de NIT con pagina y huella digital. Una mencion
NO equivale a pertenencia, adjudicacion, contrato firmado ni ejecucion.
"""
from __future__ import annotations

import hashlib
import io
import re

from index27.store import validated_url, normalize_nit

MAX_DOCUMENT_BYTES = 15_000_000
MAX_PAGES = 80
# Require the token NIT to reduce false positives from budgets, bank accounts, etc.
NIT_PATTERN = re.compile(r"\bN\.?\s*I\.?\s*T\.?\s*[:#\-]?\s*((?:\d[.\s]?){9,10})(?!\d)", re.I)


def nit_mentions(text: str, *, max_hints: int = 100) -> list[dict]:
    if not isinstance(text,str):
        raise ValueError("Texto documental invalido")
    result = []
    seen = set()
    for match in NIT_PATTERN.finditer(text):
        raw = re.sub(r"\D", "", match.group(1))
        try:
            nit = normalize_nit(raw)
        except ValueError:
            continue
        if nit in seen:
            continue
        seen.add(nit)
        snippet = " ".join(text[max(0,match.start()-100):match.end()+190].split())
        result.append({"nit":nit,"excerpt":snippet[:260],"verification_status":"indicio_no_verificado"})
        if len(result) >= max_hints:
            break
    return result


def parse_pdf(payload: bytes, *, source: str, process_ref: str, process_url: str,
              document_url: str, max_pages: int = MAX_PAGES) -> dict:
    if not isinstance(payload,bytes) or not payload.startswith(b"%PDF") or len(payload) > MAX_DOCUMENT_BYTES:
        raise ValueError("El archivo no es un PDF valido dentro del limite establecido")
    validated_url(process_url)
    validated_url(document_url)
    if not 1 <= max_pages <= MAX_PAGES:
        raise ValueError("Limite de paginas invalido")
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(payload),strict=False)
    if reader.is_encrypted:
        raise ValueError("PDF protegido: no se intenta desbloqueo")
    total = len(reader.pages)
    records = []
    for index in range(min(max_pages,total)):
        extracted = reader.pages[index].extract_text() or ""
        for hint in nit_mentions(extracted):
            records.append({"source":source,"process_ref":process_ref,
                            "process_url":process_url,"document_url":document_url,
                            "page":index+1,"nit":hint["nit"],"excerpt":hint["excerpt"],
                            "verification_status":"indicio_no_verificado"})
        if len(records)>=500:
            break
    return {"indicators":records[:500],"sha256":hashlib.sha256(payload).hexdigest(),
            "pages_reported":total,"pages_examined":min(max_pages,total),
            "truncated":total>max_pages or len(records)>=500,
            "contract_verified":False,"membership_verified":False,
            "binary_persisted":False}
