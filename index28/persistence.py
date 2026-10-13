"""Cola documental persistente y aditiva. Nunca almacena el PDF original.

Compatible con el Store PostgreSQL existente y SQLite para pruebas. Cada
revision de un documento conserva su resultado y sus incidentes por separado.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import time
import uuid

from index27.store import Store, UTC, normalize_nit, validated_url
from index28.socrata import VALID_CONSTANCIA, VALID_PORTFOLIO

DDL = (
    """CREATE TABLE IF NOT EXISTS index_doc_jobs (
      job_key TEXT PRIMARY KEY, platform TEXT NOT NULL, process_ref TEXT NOT NULL,
      document_id TEXT NOT NULL, revision TEXT NOT NULL, priority INTEGER NOT NULL,
      metadata_json TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
      lease_token TEXT, lease_until BIGINT NOT NULL, next_attempt BIGINT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_error TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS index_doc_results (
      job_key TEXT PRIMARY KEY REFERENCES index_doc_jobs(job_key),
      document_sha256 TEXT NOT NULL, result_json TEXT NOT NULL, checked_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS index_doc_observations (
      observation_key TEXT PRIMARY KEY, job_key TEXT NOT NULL REFERENCES index_doc_jobs(job_key),
      id_type TEXT NOT NULL, identification TEXT NOT NULL, page INTEGER NOT NULL,
      evidence_kind TEXT NOT NULL, observation_json TEXT NOT NULL,
      review_status TEXT NOT NULL, checked_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS index_doc_inventories (
      inventory_key TEXT PRIMARY KEY, platform TEXT NOT NULL, process_ref TEXT NOT NULL,
      snapshot_json TEXT NOT NULL, checked_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ix_doc_queue ON index_doc_jobs(status,next_attempt,priority)",
    "CREATE INDEX IF NOT EXISTS ix_doc_identification ON index_doc_observations(id_type,identification)",
)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class DocumentStore(Store):
    """No cambia las tablas ni las respuestas del indice publicado 2.7/2.10."""

    def __init__(self,url=None):
        # Reintentar solo el establecimiento de conexion, antes de cualquier
        # escritura; nunca repetir a ciegas una transaccion SQL incierta.
        for attempt in range(3):
            try:
                super().__init__(url)
                return
            except Exception as exc:
                if attempt==2 or type(exc).__name__!="OperationalError":
                    raise
                time.sleep(0.15*(attempt+1))

    @contextmanager
    def atomic(self):
        try:
            yield
            self.con.commit()
        except BaseException:
            self.con.rollback()
            raise

    def create_document_schema(self):
        with self.atomic():
            for statement in DDL:
                self.execute(statement)

    def save_inventory(self, snapshot: dict) -> str:
        platform = snapshot["platform"]
        reference = snapshot.get("reference") or snapshot.get("portfolio")
        self._reference(platform, reference)
        # Inventarios, resultados y metadatos nunca aceptan objetos binarios.
        encoded = _dump(snapshot)
        if len(encoded.encode()) > 3_000_000:
            raise ValueError("Inventario demasiado grande")
        key = digest([platform, reference, snapshot])
        with self.atomic():
            self.execute("""INSERT INTO index_doc_inventories
              (inventory_key,platform,process_ref,snapshot_json,checked_at)
              VALUES (%s,%s,%s,%s,%s) ON CONFLICT(inventory_key) DO NOTHING""",
              (key, platform, reference, encoded, UTC()))
        return key

    @staticmethod
    def _reference(platform: str, reference: str):
        pattern = {"SECOP I": VALID_CONSTANCIA, "SECOP II": VALID_PORTFOLIO}.get(platform)
        if pattern is None or not pattern.fullmatch(str(reference)):
            raise ValueError("Plataforma o referencia documental invalida")

    def enqueue(self, platform: str, reference: str, document: dict, priority: int) -> str:
        self._reference(platform, reference)
        doc_id = str(document.get("id") or document.get("document_id") or "")
        if not doc_id.isdecimal() or len(doc_id) > 14 or not 0 <= priority <= 20:
            raise ValueError("Documento o prioridad invalidos")
        # Dataset actual/historico de un mismo archivo no genera dos trabajos.
        revision = digest([document.get("name") or document.get("filename"),
                           document.get("description"), document.get("modified_at") or document.get("loaded_at"),
                           document.get("download_url_published"), document.get("metadata_version", ""),
                           document.get("reader_policy","text_v211")])
        key = digest([platform, reference, doc_id, revision])
        now = UTC()
        metadata = _dump(document)
        if len(metadata.encode()) > 20_000:
            raise ValueError("Metadatos documentales excesivos")
        with self.atomic():
            self.execute("""INSERT INTO index_doc_jobs
              (job_key,platform,process_ref,document_id,revision,priority,metadata_json,
               status,attempts,lease_token,lease_until,next_attempt,created_at,updated_at,last_error)
              VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',0,NULL,0,0,%s,%s,'')
              ON CONFLICT(job_key) DO NOTHING""",
              (key,platform,reference,doc_id,revision,priority,metadata,now,now))
        return key

    def job(self, key: str) -> dict:
        rows = self.rows("SELECT * FROM index_doc_jobs WHERE job_key=%s", (key,))
        if not rows:
            raise ValueError("Trabajo documental inexistente")
        row = rows[0]
        row["document"] = json.loads(row.pop("metadata_json"))
        return row

    def claim(self, key: str, *, now: int | None = None, lease_seconds: int = 180,
              max_attempts: int = 3) -> dict | None:
        if not 30 <= lease_seconds <= 600 or not 1 <= max_attempts <= 10:
            raise ValueError("Limites de ejecucion invalidos")
        clock = int(time.time()) if now is None else int(now)
        token = uuid.uuid4().hex
        with self.atomic():
            # Compare-and-set evita que dos workers reclamen el mismo documento.
            rows = self.rows("""UPDATE index_doc_jobs SET status='working',attempts=attempts+1,
              lease_token=%s,lease_until=%s,updated_at=%s WHERE job_key=%s
              AND attempts < %s AND next_attempt <= %s
              AND (status IN ('pending','failed') OR (status='working' AND lease_until <= %s))
              RETURNING job_key""", (token,clock+lease_seconds,UTC(),key,max_attempts,clock,clock))
        if not rows:
            return None
        return self.job(key)

    def finish(self, key: str, token: str, result: dict):
        sha = result.get("sha256", "")
        if len(sha) != 64 or any(x not in "0123456789abcdef" for x in sha):
            raise ValueError("Falta huella de documento examinado")
        if result.get("binary_persisted") is not False:
            raise ValueError("Resultado debe excluir los bytes originales")
        encoded = _dump(result)
        if len(encoded.encode()) > 2_000_000:
            raise ValueError("Resultado documental excesivo")
        status = "partial" if result.get("truncated") or result.get("unreadable_pages") or result.get("errors") else "parsed"
        observations = [("mention",h) for h in result.get("indicators",[])]
        observations += [("composition_candidate",h) for h in result.get("membership_candidates",[])]
        with self.atomic():
            rows = self.rows("""UPDATE index_doc_jobs SET status=%s,lease_token=NULL,lease_until=0,
                updated_at=%s,last_error='' WHERE job_key=%s AND status='working' AND lease_token=%s
                RETURNING job_key""",(status,UTC(),key,token))
            if not rows:
                raise ValueError("El trabajo ya no pertenece a este worker")
            self.execute("""INSERT INTO index_doc_results VALUES (%s,%s,%s,%s)
                ON CONFLICT(job_key) DO NOTHING""",(key,sha,encoded,UTC()))
            for kind, hint in observations:
                id_type = hint.get("id_type","NIT")
                raw = hint.get("identification") or hint.get("nit")
                identification = normalize_nit(raw) if id_type == "NIT" else str(raw)
                if id_type not in {"NIT","CC"} or not identification.isdecimal() or not 5 <= len(identification) <= 12:
                    raise ValueError("Identificacion documental invalida")
                page = hint["page"]
                if not isinstance(page,int) or page < 1:
                    raise ValueError("Pagina invalida")
                # Esta tabla solo contiene indicios y candidaturas; no habilita contratos.
                obs_key = digest([key,kind,id_type,identification,page,hint])
                self.execute("""INSERT INTO index_doc_observations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(observation_key) DO NOTHING""",
                    (obs_key,key,id_type,identification,page,kind,_dump(hint),"pending_review",UTC()))

    def fail(self, key: str, token: str, *, error_code: str, blocked: bool = False,
             now: int | None = None):
        # Solo codigos internos: nunca guardar respuestas completas, claves o cookies.
        if error_code not in {"http_403","http_404","http_429","http_error","download_unavailable",
                              "invalid_link","invalid_pdf","reader_failed","metadata_only"}:
            raise ValueError("Codigo de incidente desconocido")
        job = self.job(key)
        clock = int(time.time()) if now is None else int(now)
        with self.atomic():
            self.execute("""UPDATE index_doc_jobs SET status=%s,lease_token=NULL,lease_until=0,
              next_attempt=%s,last_error=%s,updated_at=%s
              WHERE job_key=%s AND status='working' AND lease_token=%s""",
              ("blocked" if blocked else "failed",clock+min(3600,60*2**min(job["attempts"],5)),
               error_code,UTC(),key,token))

    def result(self, key: str) -> dict | None:
        rows = self.rows("SELECT result_json FROM index_doc_results WHERE job_key=%s",(key,))
        return json.loads(rows[0]["result_json"]) if rows else None

    def candidates(self, raw_nit: str, limit: int = 100) -> dict:
        nit = normalize_nit(raw_nit)
        limit = min(200,max(1,int(limit)))
        rows = self.rows("""SELECT o.*,j.platform,j.process_ref,j.document_id,r.document_sha256
          FROM index_doc_observations o JOIN index_doc_jobs j ON j.job_key=o.job_key
          JOIN index_doc_results r ON r.job_key=o.job_key
          WHERE o.id_type='NIT' AND o.identification=%s
          ORDER BY o.checked_at DESC,o.observation_key LIMIT %s""",(nit,limit+1))
        out = []
        for row in rows[:limit]:
            hint = json.loads(row.pop("observation_json"))
            row["observation"] = hint
            out.append(row)
        return {"nit":nit,"observations":out,"count_observations":len(out),
                "truncated":len(rows)>limit,"verified_contracts_from_observations":0,
                "scope":"Evidencia pendiente de revision; no equivale a contratos del integrante"}

    def queue_status(self, keys: list[str]) -> list[dict]:
        return [{k:r[k] for k in ("job_key","document_id","status","attempts","last_error","updated_at")}
                for key in keys for r in [self.job(key)]]
