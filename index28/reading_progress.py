"""Progreso por pagina con huella invariable y conservación de evidencia previa."""
from __future__ import annotations
import copy
import json


def page_states(result: dict) -> dict[int,dict]:
    states={}
    for row in result.get("page_states",[]):
        number=row.get("page")
        if not isinstance(number,int) or isinstance(number,bool) or number<1:
            raise ValueError("Pagina de progreso invalida")
        if row.get("status") not in {"read","unreadable","failed","pending"}:
            raise ValueError("Estado de pagina invalido")
        states[number]=copy.deepcopy(row)
    if states:
        return states
    # Compatibilidad con resultados guardados antes de incorporar el progreso.
    total=int(result.get("pages_reported",0))
    examined=int(result.get("pages_examined",0))
    unread=set(result.get("unreadable_pages",[]))
    failed={e.get("page") for e in result.get("errors",[]) if isinstance(e,dict) and e.get("page")}
    for n in range(1,total+1):
        status="pending" if n>examined else "unreadable" if n in unread or n in failed else "read"
        states[n]={"page":n,"status":status,"attempts":int(n<=examined),
                   "method":"ocr" if n in result.get("ocr_pages",[]) else "text",
                   "error_code":"page_unreadable" if status=="unreadable" else ""}
    return states


def retryable_pages(result: dict, limit: int = 8) -> list[int]:
    if not 1<=limit<=80:
        raise ValueError("Limite de paginas invalido")
    states=page_states(result)
    total=int(result.get("pages_reported",0))
    return [n for n in range(1,total+1)
            if states.get(n,{}).get("status")!="read" and states.get(n,{}).get("attempts",0)<3][:limit]


def merge(previous: dict | None, current: dict) -> dict:
    if previous and previous["sha256"]!=current["sha256"]:
        raise ValueError("document_changed")
    out=copy.deepcopy(current)
    old=page_states(previous or {})
    new=page_states(current)
    for number,row in new.items():
        # Un resultado sin examinar esa pagina no borra un resultado anterior.
        if row["status"]=="pending":
            old.setdefault(number,row)
            continue
        before=old.get(number,{})
        row["attempts"]=int(before.get("attempts",0))+int(row.get("attempts",1))
        if before.get("status")=="read" and row["status"]!="read":
            continue
        old[number]=row
    total=int(current.get("pages_reported",(previous or {}).get("pages_reported",0)))
    if previous and total!=int(previous.get("pages_reported",total)):
        raise ValueError("Numero de paginas incoherente con la huella")
    for n in range(1,total+1):
        old.setdefault(n,{"page":n,"status":"pending","attempts":0,"method":"","error_code":""})
    if total:
        out["page_states"]=[old[n] for n in sorted(old)]
        out["pages_examined"]=sum(s["attempts"]>0 for s in old.values())
        out["pages_read"]=sum(s["status"]=="read" for s in old.values())
        out["pending_pages"]=[n for n,s in old.items() if s["status"]!="read"]
        out["unreadable_pages"]=[n for n,s in old.items() if s["status"] in {"failed","unreadable"}]
        out["ocr_pages"]=[n for n,s in old.items() if s["status"]=="read" and s.get("method")=="ocr"]
        out["errors"]=[{"page":n,"code":s.get("error_code") or "page_unreadable"}
                       for n,s in old.items() if s["status"] in {"failed","unreadable"}]
        out["evidence_truncated"]=bool((previous or {}).get("evidence_truncated")) or bool(current.get("evidence_truncated"))
        out["truncated"]=bool(out["pending_pages"]) or out["evidence_truncated"]
        out["retryable_pages"]=retryable_pages(out,80)
    for field in ("indicators","membership_candidates"):
        rows=(previous or {}).get(field,[])+current.get(field,[])
        unique={json.dumps(r,sort_keys=True,ensure_ascii=False):r for r in rows}
        # No se eliminan observaciones previas al reanudar otra pagina.
        out[field]=list(unique.values())
    out["binary_persisted"]=False
    return out
