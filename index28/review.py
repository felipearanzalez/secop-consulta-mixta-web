"""Vista de contraste: conserva contratos y estados, sin calcular capacidad residual."""
from __future__ import annotations
import copy
from datetime import date,datetime,timezone
import json
import re
from index27.store import normalize_nit,UTC
from index28.persistence import DocumentStore,digest

DDL=("""CREATE TABLE IF NOT EXISTS index_review_snapshots (
 snapshot_key TEXT PRIMARY KEY,nit TEXT NOT NULL,payload_json TEXT NOT NULL,
 source_checked_at TEXT NOT NULL,imported_at TEXT NOT NULL
)""","CREATE INDEX IF NOT EXISTS ix_review_nit ON index_review_snapshots(nit,imported_at)")


def parse_day(value: str) -> date | None:
    try:return date.fromisoformat(str(value)[:10]) if re.match(r"^\d{4}-\d{2}-\d{2}",str(value)) else None
    except ValueError:return None


def cutoff_notes(record: dict,cutoff: str) -> dict:
    day=date.fromisoformat(cutoff);raw=record.get("sourceRow") or record
    sign=parse_day(raw.get("fecha_de_firma") or raw.get("fecha_de_firma_del_contrato") or record.get("signature_date_reported"))
    start=parse_day(record.get("start") or record.get("start_date_reported"))
    end=parse_day(record.get("end") or record.get("end_date_reported"))
    state=str(record.get("state") or record.get("status_reported") or "")
    norm=state.upper()
    return {"date":cutoff,"state_as_of_cutoff_verified":False,
            "signature_after_cutoff":bool(sign and sign>day),"start_after_cutoff":bool(start and start>day),
            "published_end_before_cutoff":bool(end and end<day),
            "suspension_reported":bool(re.search(r"SUSPEND",norm)),
            "closure_reported":bool(re.search(r"TERMIN|LIQUID|CERRAD|ANULAD|CANCELAD",norm)),
            "note":"Estado reportado en la consulta guardada; las novedades a la fecha de corte requieren documentos"}


class ReviewStore(DocumentStore):
    def create_review_schema(self):
        self.create_document_schema()
        with self.atomic():
            for sql in DDL:self.execute(sql)

    def save_snapshot(self,payload: dict) -> str:
        if not isinstance(payload,dict):raise ValueError("Consulta estructurada invalida")
        identity=payload.get("identity") or {}
        nit=normalize_nit(identity.get("raw") or identity.get("base") or identity.get("nit"))
        report=payload.get("report");core=payload.get("core")
        if report is not None:
            if not isinstance(report,dict) or not isinstance(report.get("execution"),list) or not isinstance(report.get("contracts"),list):
                raise ValueError("Exportacion 2.10 invalida")
        elif not isinstance(core,dict) or not isinstance(core.get("individual"),list) or not isinstance(core.get("plural"),list):
            raise ValueError("Falta resultado del motor 2.10")
        checked=str(payload.get("at") or (core or {}).get("at") or "")
        try:
            when=datetime.fromisoformat(checked.replace("Z","+00:00"))
            if when.tzinfo is None:raise ValueError("Fecha sin zona")
            checked=when.astimezone(timezone.utc).isoformat()
        except ValueError:raise ValueError("Falta fecha de la consulta original")
        encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False)
        if len(encoded.encode())>12_000_000:raise ValueError("Consulta demasiado grande")
        key=digest([nit,payload])
        with self.atomic():
            self.execute("INSERT INTO index_review_snapshots VALUES (%s,%s,%s,%s,%s) ON CONFLICT(snapshot_key) DO NOTHING",
                         (key,nit,encoded,checked,UTC()))
        return key

    def snapshot(self,nit: str) -> dict | None:
        rows=self.rows("SELECT * FROM index_review_snapshots WHERE nit=%s ORDER BY source_checked_at DESC,imported_at DESC LIMIT 1",(normalize_nit(nit),))
        if not rows:return None
        out=rows[0];out["payload"]=json.loads(out.pop("payload_json"));return out

    def view(self,nit: str,cutoff: str,limit: int=200) -> dict:
        nit=normalize_nit(nit)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",cutoff):raise ValueError("Fecha de corte invalida")
        date.fromisoformat(cutoff)
        if not 1<=limit<=200:raise ValueError("Limite invalido")
        saved=self.snapshot(nit);payload=saved["payload"] if saved else {}
        report=payload.get("report") or {};core=payload.get("core") or {}
        source=report.get("execution",[])+report.get("contracts",[]) if "report" in payload else core.get("individual",[])+core.get("plural",[])
        # No se descarta ningun registro por estado o fechas vencidas. Tampoco se
        # fusionan contratos distintos solo porque comparten un proceso.
        records=[];seen=set()
        for number,row in enumerate(source):
            if not isinstance(row,dict):raise ValueError("Registro contractual invalido")
            key=row.get("key") or row.get("contractId") or "unresolved:"+str(number)
            if key in seen:continue
            seen.add(key);records.append({**copy.deepcopy(row),"cutoff_review":cutoff_notes(row,cutoff)})
        extended=payload.get("extended") or {}
        awards=copy.deepcopy(extended.get("awards") or [])
        for award in awards:
            award["contract_verified"]=False
            awarded=parse_day(award.get("awardDate"))
            award["award_after_cutoff"]=bool(awarded and awarded>date.fromisoformat(cutoff))
        hits=self.candidates(nit,limit=limit)
        documentary={}
        for hit in hits["observations"]:
            job=self.job(hit["job_key"]);result=self.result(hit["job_key"]) or {};doc=job["document"]
            item=documentary.setdefault(hit["job_key"],{"job_key":hit["job_key"],"platform":job["platform"],
                "process_ref":job["process_ref"],"document_id":job["document_id"],
                "document_name":doc.get("filename") or doc.get("name") or "Documento",
                "document_url":doc.get("download_url_published"),"sha256":hit["document_sha256"],
                "reading_status":job["status"],"pages_read":result.get("pages_read"),
                "pages_reported":result.get("pages_reported"),"pending_pages":result.get("pending_pages",[]),
                "observations":[],"contract_verified":False,"review_status":"pending_review"})
            item["observations"].append({"page":hit["page"],"kind":hit["evidence_kind"],**hit["observation"]})
        tasks=copy.deepcopy(report.get("tasks") or core.get("tasks") or [])
        return {"version":"2.11-r3","nit":nit,"cutoff":cutoff,"snapshot_available":bool(saved),
                "snapshot_checked_at":saved["source_checked_at"] if saved else None,
                "contracts":records,"awards":awards,"documentary_evidence":list(documentary.values()),
                "documentary_results_truncated":hits["truncated"],"source_tasks":tasks,
                "counts":{"contract_records":len(records),"suspended":sum(x["cutoff_review"]["suspension_reported"] for x in records),
                          "awards_without_contract":len(awards),"documentary_files":len(documentary)},
                "coverage":self.overview(),"asserts_absence_of_contracts":False,"national_coverage":False,
                "capacity_residual_calculated":False,
                "scope":"Contraste documental; un indicio de NIT o una adjudicacion no acredita pertenencia contractual"}

    def export(self,nit: str,cutoff: str) -> dict:
        saved=self.snapshot(nit)
        return {"review":self.view(nit,cutoff),"original_210":copy.deepcopy(saved["payload"]) if saved else None}
