"""Comando de prueba; usa exclusivamente Datos Abiertos y no escribe en PostgreSQL.

python -m index28.cli --secop-i 21-4-12343945
python -m index28.cli --secop-ii CO1.BDOS.8263083
"""
from __future__ import annotations

import argparse
import json
from index28.expediente_secop_i import expediente as consulta_i
from index28.regimen_especial_secop2 import expediente as consulta_ii


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Inventario documental experimental, sin lectura ni almacenamiento de PDF")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--secop-i",metavar="CONSTANCIA")
    group.add_argument("--secop-ii",metavar="CO1.BDOS.NUMERO")
    parser.add_argument("--page-size",type=int,default=100)
    parser.add_argument("--max-pages",type=int,default=3)
    args=parser.parse_args(argv)
    try:
        fn=consulta_i if args.secop_i else consulta_ii
        out=fn(args.secop_i or args.secop_ii,page_size=args.page_size,max_pages=args.max_pages)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if out["complete_in_requested_sources"] else 3


if __name__=="__main__":
    raise SystemExit(main())
