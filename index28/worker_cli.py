"""Operaciones manuales de la rama experimental, sin servicios ni cron nuevos."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from index28.persistence import DocumentStore
from index28.pipeline import run_process
from index28.reconciliation import reconcile,reconcile_export
from index28.discovery import seed_plural


def main(argv=None):
    parser=argparse.ArgumentParser(description="Lotes documentales y conciliacion de desarrollo")
    commands=parser.add_subparsers(dest="command",required=True)
    work=commands.add_parser("inspect",help="Inventariar, leer y guardar solo hechos del lote")
    work.add_argument("--platform",choices=["I","II"],required=True)
    work.add_argument("--reference",required=True)
    work.add_argument("--database",required=True,help="URL PostgreSQL de desarrollo o sqlite:///ruta")
    work.add_argument("--documents",type=int,default=3)
    work.add_argument("--ocr",action="store_true",help="Leer hasta ocho paginas escaneadas por archivo; requiere Tesseract spa")
    lookup=commands.add_parser("candidates",help="Consultar evidencia pendiente de revision")
    lookup.add_argument("--database",required=True)
    lookup.add_argument("--nit",required=True)
    seed=commands.add_parser("seed-secop-i",help="Descubrir expedientes plurales sin conocer el NIT de integrantes")
    seed.add_argument("--database",required=True)
    seed.add_argument("--dataset",choices=["f789-7hwg","qddk-cgux"],default="f789-7hwg")
    seed.add_argument("--partition",default="plural_initial")
    seed.add_argument("--processes",type=int,default=3)
    merge=commands.add_parser("reconcile",help="Comparar exportaciones sin escribir en la web")
    merge.add_argument("--baseline",type=Path,required=True,help="JSON con lista de registros 2.10")
    merge.add_argument("--incoming",type=Path,required=True,help="JSON {records,coverage}")
    args=parser.parse_args(argv)
    try:
        if args.command=="reconcile":
            previous=json.loads(args.baseline.read_text())
            new=json.loads(args.incoming.read_text())
            result=(reconcile_export(previous,new) if isinstance(previous,dict)
                    else reconcile(previous,new["records"],coverage=new["coverage"]))
        else:
            store=DocumentStore(args.database)
            try:
                store.create_document_schema()
                if args.command=="inspect":
                    result=run_process(store,"SECOP "+args.platform,args.reference,max_documents=args.documents,use_ocr=args.ocr)
                elif args.command=="seed-secop-i":
                    result=seed_plural(store,dataset=args.dataset,partition=args.partition,limit=args.processes)
                else:
                    result=store.candidates(args.nit)
            finally:
                store.close()
    except (ValueError,KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.command=="inspect" and not result["complete_in_requested_sources"]:
        return 3
    if args.command=="seed-secop-i" and result["status"]!="ok":
        return 3
    return 0


if __name__=="__main__":
    raise SystemExit(main())
