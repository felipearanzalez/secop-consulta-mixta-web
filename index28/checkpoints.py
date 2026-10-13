"""Marcadores de avance para un futuro indexador incremental PostgreSQL/SQLite.

No inicia tareas ni crea un cron. Evita avanzar el cursor si el lote fue parcial.
"""
from __future__ import annotations

import json
import re
from index27.store import Store, UTC
from index28.socrata import FIELDS

ALLOWED_SOURCES = frozenset((*FIELDS.keys(), "asosupro", "findeter"))

DDL = """CREATE TABLE IF NOT EXISTS index_scan_checkpoints (
 source TEXT NOT NULL,
 partition_key TEXT NOT NULL,
 cursor TEXT NOT NULL,
 last_success_at TEXT,
 last_attempt_at TEXT NOT NULL,
 status TEXT NOT NULL,
 last_count INTEGER NOT NULL,
 error TEXT NOT NULL,
 coverage_json TEXT NOT NULL,
 PRIMARY KEY(source,partition_key)
)"""


def ensure_schema(store: Store) -> None:
    store.execute(DDL)
    store.con.commit()


def _key(source: str, partition: str) -> tuple[str, str]:
    if source not in ALLOWED_SOURCES or not re.fullmatch(r"[\w.:-]{1,100}", partition):
        raise ValueError("Origen o particion de indexacion no admitidos")
    return source, partition


def read(store: Store, source: str, partition: str) -> dict | None:
    source, partition = _key(source, partition)
    rows = store.rows("SELECT * FROM index_scan_checkpoints WHERE source=%s AND partition_key=%s",(source,partition))
    if not rows:
        return None
    row = rows[0]
    row["coverage"] = json.loads(row.pop("coverage_json"))
    return row


def record(store: Store, source: str, partition: str, *, status: str, count: int,
           cursor: str = "", coverage: list[dict] | None = None, error: str = "") -> dict:
    source, partition = _key(source, partition)
    if status not in {"ok", "partial", "failed"} or count < 0 or count > 100_000:
        raise ValueError("Estado o numero de registros invalido")
    if not isinstance(cursor, str) or len(cursor) > 250 or not isinstance(error, str):
        raise ValueError("Cursor o incidente invalido")
    current = read(store, source, partition)
    # On incident, preserve last fully completed offset. Never skip unseen records.
    safe_cursor = cursor if status == "ok" else ((current or {}).get("cursor") or "")
    latest_success = UTC() if status == "ok" else ((current or {}).get("last_success_at"))
    now = UTC()
    payload = (source, partition, safe_cursor, latest_success, now, status, count,
               error[:300], json.dumps(coverage or [],ensure_ascii=False))
    store.execute("""INSERT INTO index_scan_checkpoints
      (source,partition_key,cursor,last_success_at,last_attempt_at,status,last_count,error,coverage_json)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(source,partition_key) DO UPDATE SET
      cursor=excluded.cursor,last_success_at=excluded.last_success_at,
      last_attempt_at=excluded.last_attempt_at,status=excluded.status,
      last_count=excluded.last_count,error=excluded.error,
      coverage_json=excluded.coverage_json""",payload)
    store.con.commit()
    return read(store, source, partition)
