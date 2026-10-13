"""Piloto manual trazable sobre expedientes oficiales concretos, sin publicar cambios."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from index28.persistence import DocumentStore
from index28.pipeline import catalogue_process,work_queue


def main(argv=None):
    parser=argparse.ArgumentParser(description="Ensayo documental de desarrollo con fuentes oficiales")
    parser.add_argument("--database",required=True)
    parser.add_argument("--secop-i",action="append",default=[])
    parser.add_argument("--secop-ii",action="append",default=[])
    parser.add_argument("--documents-per-i",type=int,default=1)
    parser.add_argument("--documents-per-ii",type=int,default=9)
    parser.add_argument("--rounds",type=int,default=8)
    parser.add_argument("--pages",type=int,default=3)
    parser.add_argument("--seconds",type=int,default=900)
    parser.add_argument("--ocr",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if (not args.secop_i and not args.secop_ii) or len(args.secop_i)+len(args.secop_ii)>10:
        parser.error("Se requieren entre uno y diez expedientes")
    if not 1<=args.rounds<=20 or not 1<=args.pages<=8 or not 10<=args.seconds<=900:
        parser.error("Limites de piloto invalidos")
    if not 1<=args.documents_per_i<=10 or not 1<=args.documents_per_ii<=20:
        parser.error("Cuota documental invalida")
    if len(args.secop_i)*args.documents_per_i+len(args.secop_ii)*args.documents_per_ii>100:
        parser.error("El piloto admite como maximo cien documentos seleccionados")
    if not args.database.startswith("sqlite:///") and urlsplit(args.database).hostname not in {"127.0.0.1","localhost"}:
        parser.error("El piloto requiere una base local aislada")
    started=time.monotonic();store=DocumentStore(args.database)
    report={"checked_at":datetime.now(timezone.utc).isoformat(),"catalogues":[],"rounds":[],
            "source_mode":"Consultas y descargas reales a fuentes publicas oficiales",
            "national_coverage":False,"production_database_modified":False,"originals_retained":False}
    selected=[]
    try:
        for platform,references,limit in [("SECOP I",args.secop_i,args.documents_per_i),
                                         ("SECOP II",args.secop_ii,args.documents_per_ii)]:
            for reference in references:
                catalogue=catalogue_process(store,platform,reference,use_ocr=args.ocr)
                report["catalogues"].append(catalogue)
                selected.extend(catalogue["job_keys"][:limit])
                print(json.dumps({"stage":"catalogue","platform":platform,"reference":reference,
                                  "listed":catalogue["documents_listed"],"selected":min(limit,catalogue["documents_listed"])},ensure_ascii=False),flush=True)
        selected=list(dict.fromkeys(selected))
        def update(result):
            print(json.dumps({"stage":"read","document_id":store.job(result["job_key"])["document_id"],
                  "status":result["status"],"pages_read":result.get("pages_read"),
                  "pending_pages":result.get("pending_pages"),"error":result.get("error_code")},ensure_ascii=False),flush=True)
        for number in range(args.rounds):
            if time.monotonic()-started>=args.seconds:
                break
            batch=work_queue(store,max_documents=max(1,len(selected)),max_pages_per_document=args.pages,
                 use_ocr=args.ocr,job_keys=selected,on_progress=update,max_seconds=min(900,max(10,args.seconds-int(time.monotonic()-started))))
            report["rounds"].append(batch)
            if not batch["attempted_in_batch"]:
                break
        details=[]
        for key in selected:
            job=store.job(key);result=store.result(key)
            entry={"document_id":job["document_id"],"platform":job["platform"],"reference":job["process_ref"],
                   "status":job["status"],"attempts":job["attempts"],"error":job["last_error"]}
            if result:
                entry.update({field:result.get(field) for field in ["sha256","pages_reported","pages_read","pending_pages","ocr_pages","errors","reader_version"]})
                entry.update(indicators=len(result["indicators"]),composition_candidates=len(result["membership_candidates"]),
                             contract_verified=False)
            details.append(entry)
        report.update(selected_documents=len(selected),documents=details,overview=store.overview(),
                      elapsed_seconds=round(time.monotonic()-started,2),
                      complete_selected_documents=sum(d["status"]=="parsed" for d in details),
                      unresolved_selected_documents=sum(d["status"]!="parsed" for d in details))
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({"selected":len(selected),"complete":report["complete_selected_documents"],
                          "unresolved":report["unresolved_selected_documents"]},ensure_ascii=False),flush=True)
        return 0 if not report["unresolved_selected_documents"] else 3
    finally:store.close()


if __name__=="__main__":raise SystemExit(main())
