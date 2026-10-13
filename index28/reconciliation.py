"""Conciliacion aditiva de resultados; ningun dato 2.10 se reemplaza por un indicio."""
from __future__ import annotations

import copy
import re
from index27.store import normalize_nit,validated_url

PROTECTED = ("state","status_reported","start","end","value","reference","entity",
             "share_percent","signature_date_reported","start_date_reported","end_date_reported")


def contract_key(row: dict) -> str | None:
    platform=row.get("platform")
    if platform in {"II","SECOP II"}:
        ident=str(row.get("contractId") or row.get("contract_id") or "")
        return "II|"+ident if re.fullmatch(r"CO1\.PCCNTR\.\d+",ident) else None
    if platform in {"I","SECOP I"}:
        uid=str((row.get("sourceRow") or {}).get("uid") or row.get("uid") or row.get("source_uid") or "")
        if uid:
            return "I|UID|"+uid
        constancia=str(row.get("constancia") or "")
        number=str(row.get("reference") or row.get("number") or "").strip()
        nit=row.get("contractorId") or row.get("contractor_nit_reported")
        try:
            base=normalize_nit(nit)
        except ValueError:
            return None
        if re.fullmatch(r"\d{2}-\d{1,2}-\d{1,14}",constancia) and number and number!=constancia:
            return "I|"+constancia+"|"+number+"|"+base
    # Una denominacion o un codigo de proceso no identifica un contrato por si solo.
    return None


def reviewed_association(row: dict, key: str) -> bool:
    """No basta que un importador escriba association_verified=true."""
    if row.get("association_verified") is not True or not str(row.get("reviewed_by") or "").strip():
        return False
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T.{5,40}",str(row.get("reviewed_at") or "")):
        return False
    sources=row.get("reviewed_evidence")
    if not isinstance(sources,list):
        return False
    accepted=set()
    for source in sources:
        if not isinstance(source,dict) or source.get("contract_key")!=key:
            continue
        if not isinstance(source.get("page"),int) or source["page"]<1:
            continue
        if not re.fullmatch(r"[a-f0-9]{64}",str(source.get("sha256") or "")):
            continue
        try:
            validated_url(source.get("url"))
        except ValueError:
            continue
        accepted.add(source.get("kind"))
    return {"contrato_firmado","composicion_plural"}.issubset(accepted)


def reconcile(baseline: list[dict], incoming: list[dict], *, coverage: list[dict]) -> dict:
    if not isinstance(baseline,list) or not isinstance(incoming,list) or not isinstance(coverage,list):
        raise ValueError("Entradas de conciliacion invalidas")
    groups={}
    records=[]
    pending=[]
    for number,row in enumerate(baseline):
        if not isinstance(row,dict):
            raise ValueError("Registro base invalido")
        key=contract_key(row)
        # Registros sin identificador se preservan sin inferir una coincidencia.
        internal=key or "UNRESOLVED_BASELINE|"+str(number)
        if internal in groups:
            groups[internal]["baseline_variants"].append(copy.deepcopy(row))
        else:
            merged={"contract_key":key,"record":copy.deepcopy(row),"baseline_variants":[],
                    "origins":["v2.10"],"complementary":[],"conflicts":[]}
            records.append(merged);groups[internal]=merged
    new_count=0
    for row in incoming:
        if not isinstance(row,dict):
            raise ValueError("Registro entrante invalido")
        key=contract_key(row)
        # Una candidatura documental no puede incorporarse a contratos del NIT.
        if not key or not reviewed_association(row,key):
            pending.append(copy.deepcopy(row))
            continue
        if key in groups:
            saved=groups[key]
            if row not in saved["complementary"]:
                saved["complementary"].append(copy.deepcopy(row))
            for field in PROTECTED:
                before=saved["record"].get(field)
                after=row.get(field)
                if before not in (None,"") and after not in (None,"") and before!=after:
                    conflict={"field":field,"baseline_value":before,"incoming_value":after}
                    if conflict not in saved["conflicts"]:
                        saved["conflicts"].append(conflict)
            if "documentary_index" not in saved["origins"]:
                saved["origins"].append("documentary_index")
        else:
            merged={"contract_key":key,"record":copy.deepcopy(row),"baseline_variants":[],
                    "origins":["documentary_index"],"complementary":[],"conflicts":[]}
            records.append(merged);groups[key]=merged;new_count+=1
    complete=bool(coverage) and all(c.get("status")=="ok" and not c.get("truncated") for c in coverage)
    return {"records":records,"pending_evidence":pending,"coverage":copy.deepcopy(coverage),
            "baseline_record_count":len(baseline),"baseline_records_preserved":len(baseline),
            "new_verified_records":new_count,"distinct_contract_records":len(records),
            "coverage_complete":complete,"asserts_absence_of_contracts":False,
            "conflict_count":sum(len(x["conflicts"]) for x in records)}


def reconcile_export(baseline_export: dict, incoming: dict) -> dict:
    """Acepta directamente el JSON descargado en la web 2.10, incluido Croma opcional."""
    report=baseline_export.get("report")
    if not isinstance(report,dict) or not isinstance(report.get("execution"),list) or not isinstance(report.get("contracts"),list):
        raise ValueError("Exportacion no corresponde a los resultados contractuales 2.10")
    result=copy.deepcopy(baseline_export)
    previous=report["execution"]+report["contracts"]
    base_coverage=[{**task,"status":"ok" if task.get("status")=="ok" else "partial"}
                   for task in report.get("tasks",[])]
    result["documentary_reconciliation"]=reconcile(previous,incoming["records"],
                                                  coverage=base_coverage+incoming["coverage"])
    return result
