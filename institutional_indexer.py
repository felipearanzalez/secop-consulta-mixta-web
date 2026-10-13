"""SECOP institutional portal pilot: background inventory + document-evidence index.

This program does NOT claim a legal association between a person and a contract.
No uploads, no browser login, no CAPTCHA bypass, no third-party destinations.
Coverage is limited to discovered public links; always report failures.
Requires: beautifulsoup4 and pypdf (see requirements-institutional.txt).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

from bs4 import BeautifulSoup

SOURCE_URLS = {
    "findeter": "https://www.findeter.gov.co/convocatorias",
    "asosupro": "https://contratacion.asosupro.gov.co/site/index",
}
ALLOWED_HOSTS = {
    "findeter": ("findeter.gov.co",),
    "asosupro": ("asosupro.gov.co",),
}
DOC_PRIORITY = re.compile(r"(EVALUACI|INFORME FINAL|P[ÓO]LIZA|GARANT[IÍ]A|ACTA DE INICIO|CONTRATO\s|ADJUDICACI|RUT|PROPUESTA)", re.I)
# Treat identifiers as evidence candidates only: PDF NIT presence is not proof of membership.
NIT = re.compile(r"(?<!\d)(?:N\.?I\.?T\.?\s*[:#.-]?\s*)?([89]\d{2}[. ]?\d{3}[. ]?\d{3})(?:\s*[-–]\s*\d)?(?!\d)")
PORTAL_LINK = re.compile(r"^/proceso/view\?id=[a-zA-Z0-9_-]{10,90}$")
PROCESS_ID = re.compile(r"\b(?:PAF[-A-Z0-9]{5,70}|FDT[-A-Z0-9]{5,70}|LP-\d{2,4}-\d{4}|CMA-\d{2,4}-\d{4}|SAMC-\d{2,4}-\d{4}|MC-\d{2,4}-\d{4}|PS-\d{2,4}-\d{4}|INV[-A-Z0-9]{4,40})\b", re.I)


def allowed(url: str, source: str) -> bool:
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower()
        return u.scheme == "https" and u.username is None and u.password is None and u.port in (None, 443) and any(host == d or host.endswith("." + d) for d in ALLOWED_HOSTS[source])
    except (ValueError, KeyError):
        return False


def get_public(url: str, source: str, max_bytes: int = 16_000_000) -> tuple[bytes, str]:
    if not allowed(url, source):
        raise ValueError("Host or scheme is not in the institutional allowlist")
    class SafeRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not allowed(newurl, source):
                raise ValueError("Redirect outside institutional allowlist")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    req = Request(url, headers={"User-Agent": "SECOP-Auditoria-Fuentes-Publicas/0.1 (research-indexer)", "Accept": "text/html,application/pdf"})
    with build_opener(SafeRedirect()).open(req, timeout=25) as result:
        if not allowed(result.geturl(), source):
            raise ValueError("Redirect outside institutional allowlist")
        kind = result.headers.get_content_type()
        if kind not in ("text/html", "application/pdf", "application/octet-stream"):
            raise ValueError("Unexpected document content type: " + kind)
        data = result.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Document exceeds safe processing limit")
        return data, kind


def listing(source: str, html: bytes, base: str) -> list[dict]:
    page = BeautifulSoup(html, "html.parser")
    output: dict[str, dict] = {}
    for link in page.select("a[href]"):
        label = link.get_text(" ", strip=True)
        href = str(link.get("href", "")).strip()
        url = urljoin(base, href)
        if not allowed(url, source):
            continue
        if source == "asosupro":
            path = urlparse(url).path + ("?" + urlparse(url).query if urlparse(url).query else "")
            if not PORTAL_LINK.match(path):
                continue
            tr = link.find_parent("tr")
            record_text = tr.get_text(" ", strip=True) if tr else label
            codes = PROCESS_ID.findall(record_text)
            reference = codes[0] if codes else ""
        else:
            # Findeter's public listing exposes a link on each process code.
            if not PROCESS_ID.fullmatch(label):
                continue
            tr = link.find_parent("tr")
            record_text = tr.get_text(" ", strip=True) if tr else label
            reference = label
        if not reference:
            continue
        output[url] = {"source": source, "reference": reference, "url": url, "summary": record_text[:1700]}
    return list(output.values())


def documents(source: str, html: bytes, url: str, maximum: int) -> list[dict]:
    page = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}
    for a in page.select("a[href]"):
        label = a.get_text(" ", strip=True)
        href = str(a.get("href", "")).strip()
        full = urljoin(url, href)
        if not allowed(full, source):
            continue
        tr = a.find_parent("tr")
        caption = (tr.get_text(" ", strip=True) if tr else label)[:450]
        if not DOC_PRIORITY.search(caption) and not ("pdf" in href.lower() and DOC_PRIORITY.search(label)):
            continue
        if not re.search(r"\.pdf(?:$|[?#])", full.lower()) and not re.search(r"\.pdf", caption.lower()):
            continue
        found[full] = {"label": caption, "url": full}
    # Evaluation, formation and contract documents before less relevant files.
    rank = lambda item: (0 if re.search(r"INFORME FINAL|EVALUACI|CONTRATO\s|RUT", item["label"], re.I) else 1, item["label"])
    return sorted(found.values(), key=rank)[:maximum]


def pdf_identifiers(pdf_content: bytes, page_limit: int = 100) -> list[dict]:
    if not pdf_content.startswith(b"%PDF"):
        raise ValueError("Resource is not a PDF")
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_content), strict=False)
    result = []
    for page_number, page in enumerate(reader.pages[:page_limit], 1):
        extracted = page.extract_text() or ""
        # Keep the source page and local snippet; document could mention unrelated firms.
        for m in NIT.finditer(extracted):
            nit = re.sub(r"\D", "", m.group(1))
            if len(nit) != 9:
                continue
            snippet = " ".join(extracted[max(0, m.start() - 125):m.end() + 160].split())
            result.append({"nit": nit, "page": page_number, "excerpt": snippet[:300], "association": "INDICIO SIN VERIFICAR"})
            if len(result) >= 500:
                return result
    return result


def connect_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS processes(source TEXT NOT NULL, url TEXT NOT NULL, reference TEXT NOT NULL,
       summary TEXT, checked_at TEXT, PRIMARY KEY(source,url));
    CREATE TABLE IF NOT EXISTS documents(source TEXT NOT NULL, url TEXT NOT NULL, process_url TEXT NOT NULL,
       label TEXT, hash TEXT, checked_at TEXT, status TEXT NOT NULL, error TEXT,
       PRIMARY KEY(source,url));
    CREATE TABLE IF NOT EXISTS identifier_evidence(source TEXT NOT NULL, doc_url TEXT NOT NULL,
       nit TEXT NOT NULL, page INTEGER NOT NULL, excerpt TEXT, association TEXT NOT NULL,
       PRIMARY KEY(source,doc_url,nit,page));
    CREATE INDEX IF NOT EXISTS evidence_nit ON identifier_evidence(nit);
    CREATE TABLE IF NOT EXISTS incidents(source TEXT, url TEXT, phase TEXT, error TEXT, at TEXT);
    """)
    return con


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def incident(db: sqlite3.Connection, source: str, url: str, phase: str, err: Exception) -> None:
    db.execute("INSERT INTO incidents VALUES(?,?,?,?,?)", (source, url, phase, str(err)[:350], timestamp()))


def crawl(db: sqlite3.Connection, source: str, pages: int = 1, per_process: int = 3,
          fetcher=get_public, pause: float = 0.75) -> dict:
    totals = {"source": source, "pages_attempted": 0, "processes_indexed": 0,
              "documents_extracted": 0, "evidence_indicators": 0, "errors": 0,
              "scope": "Only publicly accessible HTML/PDF. Identifiers are evidence CANDIDATES, not contractual association."}
    for page in range(pages):
        sep = "?" if "?" not in SOURCE_URLS[source] else "&"
        url = SOURCE_URLS[source] + sep + "page=" + str(page)
        totals["pages_attempted"] += 1
        try:
            html, _ = fetcher(url, source)
            rows = listing(source, html, url)
        except (ValueError, HTTPError, URLError, TimeoutError, OSError) as e:
            totals["errors"] += 1
            incident(db, source, url, "listing", e)
            continue
        for item in rows:
            db.execute("INSERT OR REPLACE INTO processes VALUES(?,?,?,?,?)",
                       (source, item["url"], item["reference"], item["summary"], timestamp()))
            totals["processes_indexed"] += 1
            try:
                detail, _ = fetcher(item["url"], source)
                docs = documents(source, detail, item["url"], per_process)
            except (ValueError, HTTPError, URLError, TimeoutError, OSError) as e:
                totals["errors"] += 1
                incident(db, source, item["url"], "details", e)
                continue
            for document in docs:
                try:
                    # Recently parsed document URLs need not be downloaded repeatedly.
                    stored = db.execute("SELECT checked_at,status FROM documents WHERE source=? AND url=?",
                                        (source,document["url"])).fetchone()
                    if stored and stored[1] == "parsed":
                        checked = datetime.fromisoformat(stored[0])
                        if (datetime.now(timezone.utc) - checked).total_seconds() < 86400:
                            continue
                    contents, _ = fetcher(document["url"], source)
                    hits = pdf_identifiers(contents)
                    digest = hashlib.sha256(contents).hexdigest()
                    db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,?,?)",
                               (source, document["url"], item["url"], document["label"], digest,
                                timestamp(), "parsed", ""))
                    db.execute("DELETE FROM identifier_evidence WHERE source=? AND doc_url=?", (source,document["url"]))
                    db.executemany("INSERT OR IGNORE INTO identifier_evidence VALUES(?,?,?,?,?,?)",
                                   [(source,document["url"],h["nit"],h["page"],h["excerpt"],h["association"]) for h in hits])
                    totals["documents_extracted"] += 1
                    totals["evidence_indicators"] += len(hits)
                except Exception as e:
                    totals["errors"] += 1
                    incident(db, source, document["url"], "document", e)
                    db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,?,?)",
                               (source,document["url"],item["url"],document["label"],"",timestamp(),"failed",str(e)[:350]))
                if pause:
                    time.sleep(pause)
            if pause:
                time.sleep(pause)
        db.commit()
    return totals


def lookup(db: sqlite3.Connection, raw_nit: str) -> list[dict]:
    nit = re.sub(r"\D", "", raw_nit.split("-")[0])
    if len(nit) != 9:
        raise ValueError("Expected nine-digit Colombian NIT without check digit")
    rows = db.execute("""SELECT e.source,p.reference,e.nit,e.page,e.excerpt,e.association,
                              d.url,p.url FROM identifier_evidence e JOIN documents d ON d.source=e.source AND d.url=e.doc_url
                       JOIN processes p ON p.source=d.source AND p.url=d.process_url
                       WHERE e.nit=? ORDER BY e.source,p.reference,e.page LIMIT 200""", (nit,)).fetchall()
    return [dict(zip(("source","reference","nit","page","excerpt","association","document_url","process_url"),r)) for r in rows]


def cli(argv=None):
    arg=argparse.ArgumentParser(description="Limited incremental evidence pilot for FINDETER / ASOSUPRO public portals")
    arg.add_argument("--database",default="portal_evidence.sqlite3")
    arg.add_argument("--source",choices=("findeter","asosupro","both"),default="both")
    arg.add_argument("--pages",type=int,default=1)
    arg.add_argument("--documents",type=int,default=3)
    arg.add_argument("--nit",default="",help="Query existing index; no downloads")
    ns=arg.parse_args(argv)
    if not (1 <= ns.pages <= 15) or not (0 <= ns.documents <= 15):
        arg.error("pages must be 1..15 and documents 0..15")
    db=connect_db(ns.database)
    try:
        if ns.nit:
            print(json.dumps({"nit":ns.nit,"results":lookup(db,ns.nit),"exhaustive":False},indent=2,ensure_ascii=False))
        else:
            for source in (("findeter","asosupro") if ns.source=="both" else (ns.source,)):
                result=crawl(db,source,pages=ns.pages,per_process=ns.documents)
                print(json.dumps(result,ensure_ascii=False))
    finally: db.commit();db.close()


if __name__=="__main__":
    cli()
