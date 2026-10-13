"""Lectura temporal, acotada y NO atributiva de un PDF publico.

Solo devuelve menciones de NIT con pagina y huella digital. Una mencion
NO equivale a pertenencia, adjudicacion, contrato firmado ni ejecucion.
"""
from __future__ import annotations

import hashlib
import io
import re

from index27.store import validated_url, normalize_nit
from index28.composition import memberships

MAX_DOCUMENT_BYTES = 15_000_000
MAX_PAGES = 80
# Require the token NIT to reduce false positives from budgets, bank accounts, etc.
NIT_PATTERN = re.compile(r"\bN\.?\s*I\.?\s*T\.?\s*[:#\-]?\s*((?:\d[.\s]?){9,10})(?!\d)", re.I)


def nit_mentions(text: str, *, max_hints: int = 100) -> list[dict]:
    if not isinstance(text,str):
        raise ValueError("Texto documental invalido")
    result = []
    seen = set()
    for match in NIT_PATTERN.finditer(text):
        raw = re.sub(r"\D", "", match.group(1))
        try:
            nit = normalize_nit(raw)
        except ValueError:
            continue
        if nit in seen:
            continue
        seen.add(nit)
        snippet = " ".join(text[max(0,match.start()-100):match.end()+190].split())
        result.append({"nit":nit,"excerpt":snippet[:260],"verification_status":"indicio_no_verificado"})
        if len(result) >= max_hints:
            break
    return result


def parse_pdf(payload: bytes, *, source: str, process_ref: str, process_url: str,
              document_url: str, max_pages: int = MAX_PAGES, use_ocr: bool = False,
              max_ocr_pages: int = 8, selected_pages: list[int] | None = None,
              resume_sha256: str | None = None) -> dict:
    if not isinstance(payload,bytes) or not payload.startswith(b"%PDF") or len(payload) > MAX_DOCUMENT_BYTES:
        raise ValueError("El archivo no es un PDF valido dentro del limite establecido")
    validated_url(process_url)
    validated_url(document_url)
    if not 1 <= max_pages <= MAX_PAGES:
        raise ValueError("Limite de paginas invalido")
    if not isinstance(use_ocr,bool) or not 1 <= max_ocr_pages <= 8:
        raise ValueError("Limite OCR invalido")
    sha=hashlib.sha256(payload).hexdigest()
    if resume_sha256 is not None and resume_sha256!=sha:
        raise ValueError("document_changed")
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(payload),strict=False)
    if reader.is_encrypted:
        raise ValueError("PDF protegido: no se intenta desbloqueo")
    total = len(reader.pages)
    if total < 1:
        raise ValueError("PDF sin paginas")
    if total>2000:
        raise ValueError("PDF excede limite total de paginas")
    if selected_pages is None:
        selection=list(range(1,min(max_pages,total)+1))
    else:
        if (not isinstance(selected_pages,list) or not 1<=len(selected_pages)<=max_pages
                or any(not isinstance(n,int) or isinstance(n,bool) or not 1<=n<=total for n in selected_pages)
                or len(set(selected_pages))!=len(selected_pages)):
            raise ValueError("Seleccion de paginas invalida")
        selection=sorted(selected_pages)
    records = []
    candidates = []
    unreadable = []
    errors = []
    examined = 0
    chars = 0
    ocr_pages = []
    states=[]
    ocr_attempts=0
    ocr_ready = False
    if use_ocr:
        import shutil,subprocess
        if shutil.which("tesseract"):
            langs=subprocess.run(["tesseract","--list-langs"],text=True,capture_output=True,timeout=5)
            ocr_ready="spa" in langs.stdout.splitlines()
        if not ocr_ready:
            errors.append({"code":"ocr_spanish_unavailable"})
    for number in selection:
        index=number-1
        examined += 1
        state={"page":number,"status":"pending","method":"text","attempts":1,
               "characters":0,"error_code":""}
        try:
            page = reader.pages[index]
            content = page.get_contents()
            if content and len(content.get_data()) > 20_000_000:
                raise ValueError("Contenido de pagina excesivo")
            extracted = (page.extract_text() or "")[:120_000]
        except Exception:
            errors.append({"page":index+1,"code":"page_not_read"})
            unreadable.append(index+1)
            state.update(status="failed",error_code="page_not_read")
            states.append(state)
            continue
        method="text"
        if len(re.sub(r"\W","",extracted)) < 20 and use_ocr and ocr_ready and ocr_attempts<max_ocr_pages:
            ocr_attempts+=1
            try:
                extracted=ocr_page(payload,index+1)
                method="ocr"
                ocr_pages.append(index+1)
            except Exception as exc:
                code=str(exc) if str(exc) in {"ocr_render_failed","ocr_timeout","ocr_engine_failed","ocr_renderer_unavailable"} else "ocr_page_failed"
                errors.append({"page":index+1,"code":code})
                state["error_code"]=code
        if len(re.sub(r"\W","",extracted)) < 20:
            unreadable.append(index+1)
            state.update(status="unreadable",error_code=state["error_code"] or (
                "ocr_spanish_unavailable" if use_ocr and not ocr_ready else "page_unreadable"))
        else:
            state["status"]="read"
        state.update(method=method,characters=len(extracted))
        states.append(state)
        chars += len(extracted)
        for hint in nit_mentions(extracted):
            records.append({"source":source,"process_ref":process_ref,
                            "process_url":process_url,"document_url":document_url,
                            "page":index+1,"nit":hint["nit"],"excerpt":hint["excerpt"],
                            "method":method,
                            "verification_status":"indicio_no_verificado"})
        for candidate in memberships(extracted,index+1,method=method):
            candidates.append({**candidate,"source":source,"process_ref":process_ref,
                               "process_url":process_url,"document_url":document_url})
        if len(records)>=500 or chars >= 1_500_000 or len(candidates) >= 500:
            break
    read={r["page"] for r in states if r["status"]=="read"}
    pending=[n for n in range(1,total+1) if n not in read]
    return {"indicators":records[:500],"sha256":sha,
            "membership_candidates":candidates[:500],
            "pages_reported":total,"pages_examined":examined,
            "pages_read":len(read),"page_states":states,"pending_pages":pending,
            "selected_pages":selection,"reader_version":"2.11-r2",
            "truncated":total>examined or len(records)>=500 or chars>=1_500_000 or len(candidates)>=500,
            "evidence_truncated":len(records)>=500 or chars>=1_500_000 or len(candidates)>=500,
            "unreadable_pages":unreadable,"errors":errors,
            "ocr_pages":ocr_pages,"ocr_requested":use_ocr,
            "contract_verified":False,"membership_verified":False,
            "binary_persisted":False}


def ocr_page(payload: bytes, page: int) -> str:
    import subprocess,tempfile,importlib.util
    from pathlib import Path
    with tempfile.TemporaryDirectory(prefix="secop_ocr_") as temp:
        path=Path(temp)/"document.pdf";path.write_bytes(payload)
        image=Path(temp)/"page"
        try:
            if importlib.util.find_spec("pypdfium2"):
                import pypdfium2 as pdfium
                # Imagen completa de la pagina, con escala acotada y sin duplicar
                # canales de color. Objetos nativos cerrados antes del OCR.
                with pdfium.PdfDocument(payload) as doc:
                    source_page=doc[page-1]
                    try:
                        width,height=source_page.get_size()
                        if width<=0 or height<=0:
                            raise ValueError("ocr_render_failed")
                        bitmap=source_page.render(scale=2200/max(width,height),grayscale=True)
                        try:
                            bitmap.to_pil().save(str(image)+".png")
                        finally:bitmap.close()
                    finally:source_page.close()
            else:
                subprocess.run(["pdftoppm","-f",str(page),"-l",str(page),"-singlefile",
                                "-scale-to","2200","-png",str(path),str(image)],
                               check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("ocr_timeout") from exc
        except Exception as exc:
            raise ValueError("ocr_render_failed") from exc
        try:
            run=subprocess.run(["tesseract",str(image)+".png","stdout","-l","spa","--psm","3"],
                               check=True,capture_output=True,text=True,timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("ocr_timeout") from exc
        except Exception as exc:
            raise ValueError("ocr_engine_failed") from exc
        return run.stdout[:120_000]


def inspect_pdf(payload: bytes, **context) -> dict:
    """PDF solo en directorio temporal eliminado al terminar, dentro de un proceso acotado."""
    import json
    import subprocess
    import sys
    import tempfile
    from pathlib import Path
    if not isinstance(payload,bytes) or len(payload)>MAX_DOCUMENT_BYTES or not payload.startswith(b"%PDF"):
        raise ValueError("invalid_pdf")
    with tempfile.TemporaryDirectory(prefix="secop_read_") as temp:
        path=Path(temp)/"document.pdf"
        path.write_bytes(payload)
        timeout=60
        if context.get("use_ocr"):
            timeout=min(300,30*min(len(context.get("selected_pages") or list(range(8))),8)+35)
        run=subprocess.run([sys.executable,"-m","index28.pdf_reader"],
                           input=json.dumps({"path":str(path),**context}),text=True,
                           capture_output=True,timeout=timeout,cwd=str(Path(__file__).resolve().parents[1]))
        if run.returncode or len(run.stdout.encode())>2_000_000:
            if '"document_changed"' in run.stdout:
                raise ValueError("document_changed")
            raise ValueError("reader_failed")
        result=json.loads(run.stdout)
        if result.get("reader_error"):
            raise ValueError("reader_failed")
        return result
