"""Subproceso acotado para documentos remotos. Solo salida JSON estructurada."""
from __future__ import annotations
import json
import sys
from pathlib import Path


def main():
    job = json.loads(sys.stdin.read(10_000))
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
        cpu=180 if job.get("use_ocr") else 45
        resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+5))
    except (ImportError,OSError,ValueError):
        pass
    from index28.evidence import parse_pdf,MAX_DOCUMENT_BYTES
    path = Path(job.pop("path"))
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("PDF demasiado grande")
    result = parse_pdf(path.read_bytes(),**job)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print('{"reader_error":"reader_failed"}')
        raise SystemExit(2)
