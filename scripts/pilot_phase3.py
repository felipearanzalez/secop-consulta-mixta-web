"""Validacion manual RENTAN/FINDETER: evidencia nueva y consulta guardada anterior."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from index28.review import ReviewStore
from index28.pipeline import catalogue_process,execute_job
from index28.portal import catalogue_portal
from index28.evidence import inspect_pdf


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True)
    parser.add_argument("--snapshot",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.database.startswith("sqlite:///") and urlsplit(args.database).hostname not in {"localhost","127.0.0.1"}:
        parser.error("Piloto en base local aislada")
    store=ReviewStore(args.database);store.create_review_schema()
    report={"checked_at":datetime.now(timezone.utc).isoformat(),"production_changed":False,
            "national_coverage":False,"original_pdf_retained":False,
            "snapshot_mode":"Consulta real guardada del motor 2.10; no se vuelve a consultar todo SECOP",
            "catalogues":[],"source_errors":[]}
    try:
        report["snapshot_key"]=store.save_snapshot(json.loads(args.snapshot.read_text()))
        try:
            rentan=catalogue_process(store,"SECOP II","CO1.BDOS.7805277")
            report["catalogues"].append({k:rentan[k] for k in ["platform","reference","documents_listed","coverage"]})
            print(json.dumps({"stage":"rentan_catalogue","documents":rentan["documents_listed"]}),flush=True)
            key=next((k for k in rentan["job_keys"] if store.job(k)["document_id"]=="597148931"),None)
            if key is None:raise ValueError("Acta no publicada en el catalogo observado")
            report["rentan_read"]=execute_job(store,key,max_pages=2)
            print(json.dumps({"stage":"rentan_read",**report["rentan_read"]}),flush=True)
        except Exception as exc:
            report["source_errors"].append({"source":"rentan","error_type":type(exc).__name__})
        try:
            findeter=catalogue_portal(store,"PAF-INVIAS-O-082-2023")
            report["catalogues"].append({k:findeter[k] for k in ["platform","reference","documents_listed","coverage"]})
            print(json.dumps({"stage":"findeter_catalogue","documents":findeter["documents_listed"]}),flush=True)
            key=next((k for k in findeter["job_keys"] if "informe_definitivo_de_verificacion" in store.job(k)["document"].get("filename","")),None)
            if key is None:raise ValueError("Informe no publicado en la ficha observada")
            # Lectura dirigida de una pagina; las otras 120 siguen pendientes.
            def directed(payload,**context):
                context["selected_pages"]=[88]
                return inspect_pdf(payload,**context)
            prior=store.result(key)
            if prior and any(p["page"]==88 and p["status"]=="read" for p in prior.get("page_states",[])):
                report["findeter_read"]={"job_key":key,"attempted":False,"reused":True,"status":store.job(key)["status"],
                                         "pages_read":prior["pages_read"],"pending_pages":prior["pending_pages"],"sha256":prior["sha256"]}
            else:
                report["findeter_read"]=execute_job(store,key,max_pages=1,parser=directed)
            print(json.dumps({"stage":"findeter_read",**report["findeter_read"]}),flush=True)
        except Exception as exc:
            report["source_errors"].append({"source":"findeter","error_type":type(exc).__name__})
        report["review"]=store.view("900102268-1","2026-09-08")
        evidence=report["review"]["documentary_evidence"]
        report["checks"]={
            "rentan_90_percent_candidate":any(d["process_ref"]=="CO1.BDOS.7805277" and any(o.get("id_base")=="900102268" and o.get("share_percent")=="90" for o in d["observations"]) for d in evidence),
            "findeter_nit_page_88":any(d["platform"]=="FINDETER" and any(o["page"]==88 and o.get("nit")=="900102268" for o in d["observations"]) for d in evidence),
            "suspended_3460_retained":any(c.get("reference")=="3460-2024" and c["cutoff_review"]["suspension_reported"] for c in report["review"]["contracts"]),
            "award_063_retained":any(a.get("portfolio")=="CO1.BDOS.9231141" for a in report["review"]["awards"])}
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({"stage":"complete","counts":report["review"]["counts"]}),flush=True)
        return 0 if all(report["checks"].values()) and not report["source_errors"] else 3
    finally:store.close()


if __name__=="__main__":raise SystemExit(main())
