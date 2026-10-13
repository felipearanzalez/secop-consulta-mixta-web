"""Consultas acotadas y auditables a inventarios oficiales de Datos Abiertos.

No realiza OCR, descarga de archivos ni atribuciones contractuales.
Todas las solicitudes se construyen con datasets/campos de lista cerrada.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from typing import Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

BASE = "https://www.datos.gov.co/resource"
FIELDS = {
    "f789-7hwg": "numero_de_constancia",
    "qddk-cgux": "numero_de_constancia",
    "tauh-5jvn": "id_proceso",
    "ps88-5e3v": "numero_de_constancia",
    "8kpz-m6cc": "numero_de_constancia",
    "jbjy-vk9h": "proceso_de_compra",
    "p6dx-8zbt": "id_del_portafolio",
    "dmgg-8hin": "proceso",
}
VALID_CONSTANCIA = re.compile(r"\d{2}-\d{1,2}-\d{1,14}\Z")
VALID_PORTFOLIO = re.compile(r"CO1\.BDOS\.\d{3,}\Z")


def exact_url(dataset: str, reference: str, limit: int = 200, offset: int = 0) -> str:
    if dataset not in FIELDS:
        raise ValueError("Conjunto no autorizado")
    pattern = VALID_PORTFOLIO if dataset in {"jbjy-vk9h", "p6dx-8zbt", "dmgg-8hin"} else VALID_CONSTANCIA
    if not pattern.fullmatch(str(reference)):
        raise ValueError("Referencia de expediente invalida")
    if not (1 <= limit <= 1000 and 0 <= offset <= 100_000):
        raise ValueError("Rango de paginacion invalido")
    params = urlencode({"$where": f"{FIELDS[dataset]}='{reference}'", "$limit": limit, "$offset": offset, "$order": ":id ASC"})
    return f"{BASE}/{dataset}.json?{params}"


def fetch_json(url: str) -> list[dict]:
    parts = urlsplit(url)
    dataset = parts.path.rsplit("/", 1)[-1].removesuffix(".json")
    if parts.scheme != "https" or parts.hostname != "www.datos.gov.co" or parts.port not in (None, 443) or \
            parts.username is not None or parts.password is not None or dataset not in FIELDS or \
            parts.path != f"/resource/{dataset}.json":
        raise ValueError("Unicamente se permiten conjuntos autorizados de datos.gov.co")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "SECOP-Consulta-Mixta-Indexer/0.3"})
    with urlopen(req, timeout=18) as stream:
        content = stream.read(3_000_001)
        if len(content) > 3_000_000:
            raise ValueError("Respuesta supera limite de lectura")
    data = json.loads(content)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("Respuesta de Socrata no es una lista de registros")
    return data


@dataclass
class Scan:
    dataset: str
    reference: str
    records: int
    status: str
    truncated: bool = False
    error: str = ""
    last_offset: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def scan_exact(dataset: str, reference: str, fetch: Callable[[str], list[dict]] = fetch_json,
               page_size: int = 200, max_pages: int = 5) -> tuple[list[dict], dict]:
    """Retorna datos parciales si falla una pagina, nunca los transforma en cero."""
    if not 1 <= page_size <= 1000 or not 1 <= max_pages <= 15 or page_size * max_pages > 7500:
        raise ValueError("Limites de lectura excedidos")
    rows: list[dict] = []
    for page in range(max_pages):
        offset = page * page_size
        url = exact_url(dataset, reference, page_size, offset)
        try:
            block = fetch(url)
            if not isinstance(block, list) or any(not isinstance(x, dict) for x in block):
                raise ValueError("Respuesta no tabular")
        except Exception as exc:
            state = "partial" if rows else "failed"
            return rows, Scan(dataset, reference, len(rows), state, error=str(exc)[:250], last_offset=offset).as_dict()
        rows.extend(block)
        if len(block) < page_size:
            return rows, Scan(dataset, reference, len(rows), "ok", last_offset=offset + len(block)).as_dict()
    try:
        extra = fetch(exact_url(dataset, reference, 1, max_pages * page_size))
        if not isinstance(extra, list):
            raise ValueError("Respuesta de prueba de limite no tabular")
        truncated = bool(extra)
    except Exception as exc:
        return rows, Scan(dataset, reference, len(rows), "partial", error="No se pudo probar exhaustividad: " + str(exc)[:190],last_offset=len(rows)).as_dict()
    return rows, Scan(dataset, reference, len(rows), "partial" if truncated else "ok",truncated=truncated,last_offset=len(rows)).as_dict()
