"""Candidaturas de composicion explicitamente relacionadas en una misma pagina.

No atribuye al adjudicatario una composicion de otro oferente ni acredita un
contrato. No toma porcentajes de amparos, representantes o experiencia.
"""
from __future__ import annotations
import re
import unicodedata

from index27.store import normalize_nit


def norm(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD",str(value)).upper()
                   if not unicodedata.combining(c))


GROUP = re.compile(r"^(?:PROPONENTE\s*:\s*)?((?:CONSORCIO|UNION TEMPORAL)\s+[A-Z0-9][A-Z0-9 .&/_-]{1,150})$")
LABELED_ID = re.compile(r"\b(?P<kind>N\.?\s*I\.?\s*T\.?|C\.?\s*C\.?)\s*[:#]?\s*"
                        r"(?P<id>\d(?:[ .]?\d){4,11}(?:\s*[-–]\s*\d)?)(?!\d)",re.I)
PERCENT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,4})?)\s*%")
EXCLUDED = re.compile(r"REPRESENTANTE|APODERADO|BENEFICIARIO|COASEGURO|DEDUCIBLE|AMPARO|VALOR ASEGURADO|INTERVENTOR|SUPERVISOR|EXPERIENCIA|ANTECEDENTE")


def memberships(text: str, page: int, *, method: str = "text") -> list[dict]:
    group = ""
    header_line = -100
    output = []
    lines = text.splitlines()
    for number,line in enumerate(lines):
        upper = norm(line.strip())
        found = GROUP.fullmatch(upper)
        if found:
            group = line.strip().split(":",1)[-1].strip()
            header_line = -100
            continue
        if re.match(r"^(?:PROPONENTE|OFERENTE|EXPERIENCIA|CONTRATOS APORTADOS)\b",upper):
            group = ""
            header_line = -100
        if not group:
            continue
        if re.search(r"INTEGRANTES|CONFORMADO POR|INTEGRADO POR|PARTICIPACION",upper) and not EXCLUDED.search(upper):
            header_line = number
        if number-header_line > 12 or EXCLUDED.search(upper):
            continue
        ids = list(LABELED_ID.finditer(line))
        if len(ids) != 1:
            continue
        ident = ids[0]
        kind = "NIT" if "N" in norm(ident["kind"]) else "CC"
        raw = re.sub(r"\s*([-–])\s*", "-", ident["id"]).strip()
        try:
            base = normalize_nit(raw) if kind == "NIT" else re.sub(r"[ .]","",raw)
        except ValueError:
            continue
        name = line[:ident.start()].strip(" |:;,-")
        name = re.sub(r"^INTEGRANTE\s*:\s*","",name,flags=re.I)
        if len(name)<3 or len(name)>200 or EXCLUDED.search(norm(name)) or GROUP.fullmatch(norm(name)):
            continue
        pcts = list(PERCENT.finditer(line[ident.end():]))
        share = None
        if len(pcts)==1:
            value = float(pcts[0][1].replace(",","."))
            if 0 < value <= 100:
                share = pcts[0][1].replace(",",".")
        output.append({"group":group,"member_name":name,"id_type":kind,
                       "identification":raw,"id_base":base,"share_percent":share,
                       "page":page,"method":method,"excerpt":line.strip()[:400],
                       "verification_status":"candidato_composicion_pendiente_revision",
                       "contract_attribution":False})
    # PDF de tablas: el orden de contenido puede unir nombre, NIT y porcentaje
    # en un parrafo aunque visualmente ocupen tres lineas de la misma celda.
    explicit=paragraph_memberships(text,page,method=method)
    keys={(x["group"],x["id_type"],x["id_base"]) for x in explicit}
    return explicit+[x for x in output if (x["group"],x["id_type"],x["id_base"]) not in keys]


def paragraph_memberships(text: str, page: int, *, method: str) -> list[dict]:
    upper=norm(text)
    markers=list(re.finditer(r"\b(?:INTEGRAD[OA]S?|CONFORMAD[OA]S?)\s+POR\s*:",upper))
    out=[]
    for pos,mark in enumerate(markers):
        previous=upper[max(0,mark.start()-1500):mark.start()]
        # Un encabezado de experiencia invalida el bloque actual hasta otro
        # proponente explicito; no se atribuye experiencia a la oferta actual.
        if re.search(r"EXPERIENCIA|CONTRATOS APORTADOS|ANTECEDENTE",previous):
            continue
        labels=list(re.finditer(r"\b(CONSORCIO|UNION TEMPORAL)\s+",previous))
        if not labels:
            continue
        # Un salto visual puede separar "CONSORCIO" de su nombre en el PDF.
        segment=re.sub(r"\s+"," ",previous[labels[-1].start():])
        group_text=re.split(r"\bNOMBRE OFERENTE|\bREPRESENTANTE|\bPROPONENTE|\bINFORMACION|\bIDENTIFICAD[OA]|\bN\.?I\.?T|[\n|;,]",segment,maxsplit=1)[0].strip(" :")
        if not GROUP.fullmatch(group_text):
            continue
        end=markers[pos+1].start() if pos+1<len(markers) else len(upper)
        block=text[mark.end():end][:5000]
        stop=re.search(r"\b(?:INFORME\s+DE\s+EVALUACION|ASPECTOS\s+JURIDICOS|REQUISITOS\s+HABILITANTES|EXPERIENCIA|CONTRATOS APORTADOS|PROPONENTE\s+(?:NO|N[Oº°]|\d))\b",norm(block))
        if stop:
            block=block[:stop.start()]
        # El cierre de la clausula no pertenece al ultimo integrante. Sin este
        # corte, una referencia posterior al supervisor borraba su candidatura.
        close=re.search(r"\b(?:Y\s+QUIEN|QUIENES\s+HAN|QUIEN\s+PARA|SE\s+HA\s+CONVENIDO|EL\s+CONTRATISTA[,;])\b",norm(block))
        if close:
            block=block[:close.start()]
        ids=list(LABELED_ID.finditer(block))
        for n,ident in enumerate(ids):
            before=block[ids[n-1].end() if n else 0:ident.start()]
            after=block[ident.end():ids[n+1].start() if n+1<len(ids) else len(block)]
            # El siguiente nombre queda antes de su NIT, tras el porcentaje anterior.
            if "%" in before:
                before=before.rsplit("%",1)[-1]
                before=re.sub(r"^\s*(?:DE\s+PARTICIPACI[ÓO]N\s*)?\)?\s*Y\s+","",before,flags=re.I)
            name=re.sub(r"^\s*\d+[.)]\s*","",before.strip()).strip(" |:;,-\n")
            if not 3<=len(name)<=200 or EXCLUDED.search(norm(name)) or EXCLUDED.search(norm(after)):
                continue
            raw=re.sub(r"\s*[-–]\s*","-",ident["id"]).strip()
            kind="NIT" if "N" in norm(ident["kind"]) else "CC"
            try:
                base=normalize_nit(raw) if kind=="NIT" else re.sub(r"[ .]","",raw)
            except ValueError:
                continue
            pcts=list(PERCENT.finditer(after))
            share=None
            if len(pcts)==1 and 0<float(pcts[0][1].replace(",","."))<=100:
                share=pcts[0][1].replace(",",".")
            out.append({"group":group_text,"member_name":name,"id_type":kind,
                        "identification":raw,"id_base":base,"share_percent":share,
                        "page":page,"method":method,"excerpt":(name+" "+ident.group()+" "+after[:120]).strip()[:400],
                        "verification_status":"candidato_composicion_pendiente_revision",
                        "contract_attribution":False})
    return out
