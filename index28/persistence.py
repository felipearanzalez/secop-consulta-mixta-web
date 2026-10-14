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
from index28.reading_progress import merge as merge_reading,retryable_pages

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
    """CREATE TABLE IF NOT EXISTS index_doc_result_versions (
      version_key TEXT PRIMARY KEY, job_key TEXT NOT NULL REFERENCES index_doc_jobs(job_key),
      result_json TEXT NOT NULL, checked_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS index_doc_access_state (
      platform TEXT NOT NULL, process_ref TEXT NOT NULL, error_code TEXT NOT NULL,
      next_retry BIGINT NOT NULL, checked_at TEXT NOT NULL,
      PRIMARY KEY(platform,process_ref)
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
        if platform=="FINDETER":
            import re
            if not re.fullmatch(r"PAF-[A-Z0-9-]{5,70}",str(reference)):
                raise ValueError("Referencia institucional invalida")
            return
        pattern = {"SECOP I": VALID_CONSTANCIA, "SECOP II": VALID_PORTFOLIO}.get(platform)
        if pattern is None or not pattern.fullmatch(str(reference)):
            raise ValueError("Plataforma o referencia documental invalida")

    def enqueue(self, platform: str, reference: str, document: dict, priority: int) -> str:
        self._reference(platform, reference)
        doc_id = str(document.get("id") or document.get("document_id") or "")
        valid_id=(doc_id.startswith("FDT.") and len(doc_id)==36 and all(c in "0123456789abcdef" for c in doc_id[4:])) if platform=="FINDETER" else doc_id.isdecimal() and len(doc_id)<=14
        if not valid_id or not 0 <= priority <= 20:
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
              max_attempts: int = 3, resume_partial: bool = False) -> dict | None:
        if not 30 <= lease_seconds <= 600 or not 1 <= max_attempts <= 10:
            raise ValueError("Limites de ejecucion invalidos")
        clock = int(time.time()) if now is None else int(now)
        if resume_partial:
            previous=self.result(key)
            if not previous or not retryable_pages(previous):
                return None
        token = uuid.uuid4().hex
        with self.atomic():
            # Compare-and-set evita que dos workers reclamen el mismo documento.
            rows = self.rows("""UPDATE index_doc_jobs SET status='working',attempts=attempts+1,
              lease_token=%s,lease_until=%s,updated_at=%s WHERE job_key=%s
              AND next_attempt <= %s
              AND ((attempts < %s AND (status IN ('pending','failed')
                    OR (status='blocked' AND last_error='http_403') OR (status='working' AND lease_until <= %s)))
                   OR (status='partial' AND attempts < 64 AND %s=1))
              RETURNING job_key""", (token,clock+lease_seconds,UTC(),key,clock,max_attempts,clock,int(resume_partial)))
        if not rows:
            return None
        return self.job(key)

    def finish(self, key: str, token: str, result: dict):
        sha = result.get("sha256", "")
        if len(sha) != 64 or any(x not in "0123456789abcdef" for x in sha):
            raise ValueError("Falta huella de documento examinado")
        if result.get("binary_persisted") is not False:
            raise ValueError("Resultado debe excluir los bytes originales")
        previous=self.result(key)
        result=merge_reading(previous,result)
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
            # Auditoria aditiva: el resultado anterior permanece recuperable.
            for version in [v for v in [previous,result] if v]:
                self.execute("""INSERT INTO index_doc_result_versions VALUES (%s,%s,%s,%s)
                  ON CONFLICT(version_key) DO NOTHING""",(digest([key,version]),key,_dump(version),UTC()))
            self.execute("""INSERT INTO index_doc_results VALUES (%s,%s,%s,%s)
                ON CONFLICT(job_key) DO UPDATE SET document_sha256=excluded.document_sha256,
                  result_json=excluded.result_json,checked_at=excluded.checked_at""",(key,sha,encoded,UTC()))
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
                              "invalid_link","invalid_pdf","reader_failed","metadata_only","document_changed"}:
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

    def source_block(self,platform: str,reference: str,*,now: int | None=None) -> dict | None:
        clock=int(time.time()) if now is None else int(now)
        rows=self.rows("""SELECT * FROM index_doc_access_state WHERE platform=%s
          AND (process_ref=%s OR process_ref='*') AND next_retry>%s
          ORDER BY next_retry DESC""",(platform,reference,clock))
        return rows[0] if rows else None

    def defer_source(self,platform: str,reference: str,error_code: str,*,now: int | None=None):
        self._reference(platform,reference)
        if error_code!="http_403":
            raise ValueError("Incidente de fuente no admitido")
        # El portal SECOP I se enfria tras el 403 para evitar solicitudes en
        # cadena. SECOP II solo pausa el expediente afectado.
        partition="*" if platform=="SECOP I" else reference
        clock=int(time.time()) if now is None else int(now)
        with self.atomic():
            self.execute("""INSERT INTO index_doc_access_state VALUES (%s,%s,%s,%s,%s)
              ON CONFLICT(platform,process_ref) DO UPDATE SET error_code=excluded.error_code,
              next_retry=excluded.next_retry,checked_at=excluded.checked_at""",
              (platform,partition,error_code,clock+3600,UTC()))

    def ready_jobs(self,limit: int=20,*,now: int | None=None) -> list[str]:
        if not 1<=limit<=100:
            raise ValueError("Limite de cola invalido")
        clock=int(time.time()) if now is None else int(now)
        rows=self.rows("""SELECT j.job_key,j.status FROM index_doc_jobs j
          WHERE j.next_attempt<=%s
            AND ((j.attempts<3 AND (j.status IN ('pending','failed')
                  OR (j.status='blocked' AND j.last_error='http_403') OR (j.status='working' AND j.lease_until<=%s)))
                 OR (j.status='partial' AND j.attempts<64))
            AND NOT EXISTS (SELECT 1 FROM index_doc_access_state a WHERE a.platform=j.platform
              AND (a.process_ref=j.process_ref OR a.process_ref='*') AND a.next_retry>%s)
          ORDER BY j.priority,j.created_at,j.job_key LIMIT %s""",(clock,clock,clock,min(1000,limit*10)))
        accepted=[]
        for row in rows:
            if row["status"]=="partial" and not retryable_pages(self.result(row["job_key"]) or {}):
                continue
            accepted.append(row["job_key"])
            if len(accepted)==limit:break
        return accepted

    def overview(self) -> dict:
        states=self.rows("SELECT platform,status,count(*) AS n FROM index_doc_jobs GROUP BY platform,status ORDER BY platform,status")
        originals=self.rows("""SELECT count(*) AS n FROM
          (SELECT platform,process_ref,document_id FROM index_doc_jobs GROUP BY platform,process_ref,document_id) x""")[0]["n"]
        sources=self.rows("SELECT platform,process_ref,error_code,next_retry,checked_at FROM index_doc_access_state")
        observations=self.rows("SELECT count(*) AS n FROM index_doc_observations")[0]["n"]
        return {"document_count":originals,"job_revision_count":sum(r["n"] for r in states),
                "states":states,"source_incidents":sources,"observation_count":observations,
                "documents_stored":0,"national_coverage":False,
                "absence_of_contracts_certified":False}
