"""Small persistent index for sourced contract facts. SQLite tests; PostgreSQL production.

No PDF/Word bytes are persisted. Caller-provided structured facts must pass evidence
validation. This index is evidence-backed but does not certify contractual execution.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse

UTC = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
TRUSTED_SOURCE_HOSTS = (
    "contratacion.asosupro.gov.co", "asosupro.gov.co", "secop.gov.co",
    "community.secop.gov.co", "www.contratos.gov.co", "contratos.gov.co",
    "www.datos.gov.co", "datos.gov.co", "findeter.gov.co", "www.findeter.gov.co",
)
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS index_contracts (
        contract_key TEXT PRIMARY KEY, jurisdiction TEXT NOT NULL, platform TEXT NOT NULL,
        entity_name TEXT NOT NULL, process_ref TEXT NOT NULL, notice_uid TEXT,
        contract_ref TEXT NOT NULL, contractor TEXT NOT NULL, contractor_nit TEXT,
        contract_value_cop BIGINT, sign_date TEXT,
        execution_class TEXT NOT NULL, execution_end_date TEXT,
        process_url TEXT NOT NULL, verification_method TEXT NOT NULL,
        indexed_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS index_memberships (
        contract_key TEXT NOT NULL, member_nit TEXT NOT NULL, member_name TEXT NOT NULL,
        share_percent TEXT NOT NULL, proof_status TEXT NOT NULL,
        PRIMARY KEY(contract_key,member_nit),
        FOREIGN KEY(contract_key) REFERENCES index_contracts(contract_key)
    )""",
    """CREATE TABLE IF NOT EXISTS index_sources (
        contract_key TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL,
        url TEXT NOT NULL, page INTEGER, note TEXT NOT NULL, document_sha256 TEXT,
        checked_at TEXT NOT NULL,
        PRIMARY KEY(contract_key,kind,url),
        FOREIGN KEY(contract_key) REFERENCES index_contracts(contract_key)
    )""",
    """CREATE TABLE IF NOT EXISTS index_indicators (
        hint_key TEXT PRIMARY KEY, source TEXT NOT NULL, process_ref TEXT NOT NULL,
        nit TEXT NOT NULL, process_url TEXT NOT NULL, document_url TEXT NOT NULL,
        document_page INTEGER NOT NULL, excerpt TEXT, verification_status TEXT NOT NULL,
        checked_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS index_incidents (
        incident_key TEXT PRIMARY KEY, source TEXT NOT NULL, stage TEXT NOT NULL,
        url TEXT, message TEXT NOT NULL, occurred_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ix_index_members_nit ON index_memberships(member_nit)",
    "CREATE INDEX IF NOT EXISTS ix_index_indicators_nit ON index_indicators(nit)",
]


def normalize_nit(value: str) -> str:
    raw = str(value).strip()
    if not re.fullmatch(r"[0-9 .\-]{8,22}", raw):
        raise ValueError("NIT invalido; use solo numeros, puntos y guiones")
    base = raw.split("-")[0]
    digits = re.sub(r"\D", "", base)
    if len(digits) == 10 and raw.find("-") < 0:
        # NIT followed by its one-digit verification digit without separator.
        digits = digits[:9]
    if len(digits) != 9:
        raise ValueError("El indice inicial requiere NIT de nueve digitos")
    return digits


def validated_url(url: str) -> str:
    u = urlparse(str(url))
    host = (u.hostname or "").lower()
    if (u.scheme != "https" or u.username is not None or u.password is not None
            or u.port not in (None, 443) or host not in TRUSTED_SOURCE_HOSTS):
        raise ValueError("Fuente externa no permitida")
    return str(url)


def validate_contract(record: dict) -> dict:
    if not isinstance(record, dict):
        raise ValueError("Se requiere un registro estructurado")
    if not record.get("contract_key") or not record.get("contract_ref"):
        raise ValueError("Falta identificador de contrato firmado")
    if record.get("execution_class") not in (
        "firma_acreditada_ejecucion_no_verificada", "ejecucion_reportada", "ejecucion_posible"
    ):
        raise ValueError("Estado documental no reconocido")
    validated_url(record["process_url"])
    if record.get("contractor_nit"):
        normalize_nit(record["contractor_nit"])
    evidence = record.get("evidence") or []
    kinds = {v.get("kind") for v in evidence if isinstance(v, dict)}
    if not {"contrato_firmado", "composicion_plural"}.issubset(kinds):
        raise ValueError("No hay prueba documental de contrato y composicion")
    for item in evidence:
        validated_url(item["url"])
        if item.get("page") is not None and (not isinstance(item["page"], int) or item["page"] < 1):
            raise ValueError("Pagina documental invalida")
    members = record.get("members") or []
    if not members:
        raise ValueError("No hay integrantes documentados")
    seen = set()
    try:
        total = Decimal(0)
        for m in members:
            nit = normalize_nit(m["nit"])
            if nit in seen or not m.get("name"):
                raise ValueError("Integrante repetido o sin razon social")
            seen.add(nit)
            p = Decimal(str(m["share_percent"]))
            if not 0 < p <= 100:
                raise ValueError("Porcentaje fuera de rango")
            total += p
        if total != Decimal(100):
            raise ValueError("La sumatoria de participaciones debe ser 100 por ciento")
    except (InvalidOperation, KeyError) as e:
        raise ValueError("No se pudo validar la composicion plural") from e
    return record


class Store:
    def __init__(self, url=None):
        self.url = url or os.getenv("DATABASE_URL", "")
        if self.url.startswith("sqlite:///"):
            path = self.url[10:]
            self.pg = False
            self.con = sqlite3.connect(path, check_same_thread=False, timeout=10)
            self.con.row_factory = sqlite3.Row
            self.con.execute("PRAGMA foreign_keys = ON")
        elif self.url.startswith(("postgresql://", "postgres://")):
            from psycopg import connect
            from psycopg.rows import dict_row
            self.pg = True
            self.con = connect(self.url, row_factory=dict_row, connect_timeout=12)
        else:
            raise ValueError("DATABASE_URL persistente obligatorio: no usar almacenamiento volatil en produccion")

    def execute(self, sql, args=()):
        if not self.pg:
            sql = sql.replace("%s", "?")
        return self.con.execute(sql, args)

    def rows(self, sql, args=()):
        return [dict(r) for r in self.execute(sql, args).fetchall()]

    def create_schema(self):
        for sql in SCHEMA:
            self.execute(sql)
        self.con.commit()

    def insert_verified(self, record: dict):
        r = validate_contract(record)
        when = UTC()
        fields = ["contract_key", "jurisdiction", "platform", "entity_name", "process_ref",
                  "notice_uid", "contract_ref", "contractor", "contractor_nit", "contract_value_cop",
                  "sign_date", "execution_class", "execution_end_date", "process_url",
                  "verification_method", "indexed_at"]
        values = [r.get(f) if f != "indexed_at" else when for f in fields]
        self.execute("INSERT INTO index_contracts ("+",".join(fields)+") VALUES ("+",".join(["%s"]*len(fields))+") "
                     "ON CONFLICT(contract_key) DO UPDATE SET indexed_at=excluded.indexed_at,"
                     "execution_class=excluded.execution_class,verification_method=excluded.verification_method", values)
        for m in r["members"]:
            self.execute("INSERT INTO index_memberships (contract_key,member_nit,member_name,share_percent,proof_status) "
                         "VALUES (%s,%s,%s,%s,%s) ON CONFLICT(contract_key,member_nit) DO UPDATE SET "
                         "member_name=excluded.member_name,share_percent=excluded.share_percent,proof_status=excluded.proof_status",
                         (r["contract_key"],normalize_nit(m["nit"]),m["name"],str(m["share_percent"]),"acreditada_en_poliza"))
        for e in r["evidence"]:
            self.execute("INSERT INTO index_sources (contract_key,kind,label,url,page,note,document_sha256,checked_at) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                         "ON CONFLICT(contract_key,kind,url) DO UPDATE SET checked_at=excluded.checked_at,"
                         "label=excluded.label, note=excluded.note",
                         (r["contract_key"],e["kind"],e["label"],e["url"],e.get("page"),
                          e.get("note", ""),e.get("document_sha256"),when))
        self.con.commit()

    def import_cases(self, path: Path | str):
        items = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in items:
            self.insert_verified(item)
        return len(items)

    def upsert_indicator(self, item: dict):
        """Unreviewed NIT mention: cannot be included as a contract or membership."""
        import hashlib
        source = item["source"]
        process_url = validated_url(item["process_url"])
        document_url = validated_url(item["document_url"])
        nit = normalize_nit(item["nit"])
        page = int(item["page"])
        if page < 1:
            raise ValueError("Pagina invalida")
        key = hashlib.sha256((source+"|"+document_url+"|"+nit+"|"+str(page)).encode()).hexdigest()
        self.execute("INSERT INTO index_indicators (hint_key,source,process_ref,nit,process_url,document_url,document_page,excerpt,verification_status,checked_at) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(hint_key) DO UPDATE SET "
                     "excerpt=excluded.excerpt,checked_at=excluded.checked_at",
                     (key,source,item["process_ref"],nit,process_url,document_url,page,
                      str(item.get("excerpt") or "")[:260],"indicio_no_verificado",UTC()))
        self.con.commit()

    def find(self, raw_nit: str, limit=30):
        nit = normalize_nit(raw_nit)
        limit = max(1,min(50,int(limit)))
        members = self.rows("""SELECT c.*,m.member_nit,m.member_name,m.share_percent,m.proof_status
            FROM index_memberships m JOIN index_contracts c ON c.contract_key=m.contract_key
            WHERE m.member_nit=%s ORDER BY c.sign_date DESC,c.contract_key LIMIT %s""",(nit,limit))
        for row in members:
            row["sources"] = self.rows("""SELECT kind,label,url,page,note,checked_at
                 FROM index_sources WHERE contract_key=%s ORDER BY kind""",(row["contract_key"],))
        hints = self.rows("""SELECT source,process_ref,process_url,document_url,document_page,verification_status,checked_at
                FROM index_indicators WHERE nit=%s ORDER BY checked_at DESC LIMIT %s""",(nit,limit))
        counts = self.rows("SELECT count(*) AS n FROM index_contracts")
        return {
            "nit":nit, "contracts":members, "indicators":hints,
            "count_contracts":len(members), "count_indicators":len(hints),
            "index_contracts_total":counts[0]["n"],
            "coverage": "Indice documental piloto; cobertura incompleta, no certifica ausencia de contratos ni ejecucion.",
            "generated_at":UTC(),
        }

    def close(self):
        self.con.close()
