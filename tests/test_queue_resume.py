"""Reanudacion efectiva, archivos cambiados y tratamiento de bloqueos de fuente."""
from __future__ import annotations
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from reportlab.pdfgen.canvas import Canvas
from index28.persistence import DocumentStore
from index28.pipeline import run_process,work_queue,execute_job
from index28.reading_progress import merge,retryable_pages
from index28.evidence import parse_pdf,inspect_pdf
import test_document_pipeline as fixtures


def multipage_pdf():
    stream=io.BytesIO();canvas=Canvas(stream)
    for nit in ["900317964-1","800143586-1","901601837-5"]:
        canvas.drawString(30,760,"Informacion contractual NIT "+nit)
        canvas.showPage()
    canvas.save();return stream.getvalue()


class QueueResumeTests(unittest.TestCase):
    setUp=fixtures.PersistenceTests.setUp
    tearDown=fixtures.PersistenceTests.tearDown
    open=fixtures.PersistenceTests.open

    def test_resume_three_batches_reads_only_pending_pages(self):
        data=multipage_pdf()
        uri="https://www.contratos.gov.co/archivos/PROCESO_"+fixtures.REF+"_123.pdf"
        snapshot=fixtures.snapshot([fixtures.document(url=uri)])
        selected=[]
        def parser(payload,**context):
            selected.append(context.get("selected_pages"))
            return parse_pdf(payload,**context)
        first=run_process(self.store,"SECOP I",fixtures.REF,inventory=snapshot,
            download_i=lambda *args:data,parser=parser,max_pages_per_document=1)
        self.assertEqual(first["jobs"][0]["status"],"partial")
        key=first["jobs"][0]["job_key"]
        self.store.close();self.store=self.open()
        for remaining in [1,0]:
            report=work_queue(self.store,max_documents=1,max_pages_per_document=1,
                             download_i=lambda *args:data,parser=parser)
            self.assertEqual(report["attempted_in_batch"],1)
            result=self.store.result(key)
            self.assertEqual(len(result["pending_pages"]),remaining)
        self.assertEqual(selected,[None,[2],[3]])
        self.assertEqual(self.store.result(key)["pages_read"],3)
        self.assertEqual(self.store.job(key)["status"],"parsed")
        for nit in ["900317964","800143586","901601837"]:
            self.assertEqual(self.store.candidates(nit)["count_observations"],1)
        self.assertEqual(self.store.rows("SELECT count(*) AS n FROM index_doc_result_versions")[0]["n"],3)

    def test_changed_bytes_cannot_merge_old_pages(self):
        payload=multipage_pdf()
        doc=fixtures.document(url="https://www.contratos.gov.co/archivos/PROCESO_"+fixtures.REF+"_123.pdf")
        first=run_process(self.store,"SECOP I",fixtures.REF,inventory=fixtures.snapshot([doc]),
                          download_i=lambda *args:payload,max_pages_per_document=1)
        key=first["jobs"][0]["job_key"]
        before=copy.deepcopy(self.store.result(key))
        response=execute_job(self.store,key,download_i=lambda *args:fixtures.pdf(["Otra version del archivo NIT 900317964-1"]))
        self.assertEqual(response["error_code"],"document_changed")
        self.assertEqual(self.store.result(key),before)
        self.assertEqual(self.store.job(key)["status"],"blocked")
        self.assertEqual(self.store.candidates("900317964")["count_observations"],1)

    def test_source_403_pauses_other_secop_i_jobs_but_ii_continues(self):
        keys=[self.store.enqueue("SECOP I",fixtures.REF,fixtures.document(str(n)),0) for n in [120,121,122]]
        url="https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592"
        ii=self.store.enqueue("SECOP II",fixtures.BDOS,
             {"document_id":"625136592","filename":"Contrato.pdf","source":"dmgg-8hin","download_url_published":url},2)
        calls=[]
        def denied(url,reference):
            calls.append(reference);raise HTTPError(url,403,"Forbidden",{},None)
        report=work_queue(self.store,max_documents=4,html_i=denied,
                          download_ii=lambda url:fixtures.pdf(["Entidad publica NIT 800143586-1"]))
        self.assertEqual(len(calls),1)
        self.assertEqual(report["attempted_in_batch"],2)
        self.assertEqual(self.store.job(ii)["status"],"parsed")
        self.assertFalse(self.store.overview()["absence_of_contracts_certified"])
        ready=self.store.ready_jobs()
        self.assertTrue(all(key not in ready for key in keys))

    def test_failed_page_can_retry_without_losing_successful_page(self):
        key=self.store.enqueue("SECOP I",fixtures.REF,fixtures.document(),0)
        def output(states,hints):
            return {"sha256":"a"*64,"binary_persisted":False,"pages_reported":2,
                    "page_states":states,"indicators":hints,"membership_candidates":[]}
        original=output([{"page":1,"status":"read","attempts":1,"method":"text"},
                         {"page":2,"status":"failed","attempts":1,"error_code":"ocr_timeout"}],
                        [{"nit":"900317964","page":1,"excerpt":"Evidencia pagina uno"}])
        job=self.store.claim(key);self.store.finish(key,job["lease_token"],original)
        retried=output([{"page":2,"status":"read","attempts":1,"method":"ocr"}],
                       [{"nit":"800143586","page":2,"excerpt":"Evidencia pagina dos"}])
        job=self.store.claim(key,resume_partial=True);self.store.finish(key,job["lease_token"],retried)
        result=self.store.result(key)
        self.assertEqual(result["pending_pages"],[])
        self.assertEqual(result["pages_read"],2)
        self.assertEqual(result["errors"],[])
        self.assertEqual(len(result["indicators"]),2)
        self.assertEqual(self.store.candidates("900317964")["count_observations"],1)

    def test_403_job_can_resume_after_source_cooldown(self):
        uri="https://www.contratos.gov.co/archivos/PROCESO_"+fixtures.REF+"_123.pdf"
        key=self.store.enqueue("SECOP I",fixtures.REF,fixtures.document(url=uri),0)
        def denied(*args):
            raise HTTPError(uri,403,"Forbidden",{},None)
        response=execute_job(self.store,key,download_i=denied)
        self.assertEqual(response["status"],"blocked")
        future=self.store.source_block("SECOP I",fixtures.REF)["next_retry"]+1
        self.assertIn(key,self.store.ready_jobs(now=future))
        with patch("index28.persistence.time.time",return_value=future):
            response=execute_job(self.store,key,download_i=lambda *args:fixtures.pdf(["Datos NIT 900317964-1 contrato"]))
        self.assertTrue(response["attempted"])
        self.assertEqual(response["status"],"parsed")
        self.assertEqual(self.store.candidates("900317964")["count_observations"],1)

    def test_page_attempts_are_bounded_and_failures_remain_visible(self):
        key=self.store.enqueue("SECOP I",fixtures.REF,fixtures.document(),0)
        output={"sha256":"b"*64,"binary_persisted":False,"pages_reported":1,
                "page_states":[{"page":1,"status":"failed","attempts":1,"error_code":"ocr_timeout"}],
                "indicators":[],"membership_candidates":[]}
        for n in range(3):
            job=self.store.claim(key,resume_partial=n>0)
            self.assertIsNotNone(job)
            self.store.finish(key,job["lease_token"],output)
        self.assertEqual(self.store.result(key)["pending_pages"],[1])
        self.assertIsNone(self.store.claim(key,resume_partial=True))
        self.assertNotIn(key,self.store.ready_jobs())
        self.assertEqual(self.store.job(key)["status"],"partial")

    def test_no_coincidence_is_still_a_completed_read_not_verified_contract(self):
        data=fixtures.pdf(["Contenido completo sin identificacion de personas o integrantes"])
        doc=fixtures.document(url="https://www.contratos.gov.co/archivos/PROCESO_"+fixtures.REF+"_123.pdf")
        report=run_process(self.store,"SECOP I",fixtures.REF,inventory=fixtures.snapshot([doc]),download_i=lambda *args:data)
        self.assertTrue(report["complete_in_requested_sources"])
        self.assertEqual(self.store.candidates("900317964")["count_observations"],0)
        self.assertFalse(self.store.overview()["absence_of_contracts_certified"])


class ReadingProgressTests(unittest.TestCase):
    def test_legacy_result_yields_exact_missing_pages(self):
        old={"pages_reported":8,"pages_examined":8,"ocr_pages":[1,3,7,8],
             "unreadable_pages":[2,4,5,6],"errors":[]}
        self.assertEqual(retryable_pages(old),[2,4,5,6])

    def test_invalid_page_selection_rejected(self):
        data=multipage_pdf()
        context=dict(source="ps88-5e3v",process_ref=fixtures.REF,process_url=fixtures.PROCESS,
                     document_url="https://www.contratos.gov.co/archivos/test.pdf")
        for pages in [[0],[4],[1,1],[True],[],["1"]]:
            with self.assertRaises(ValueError):parse_pdf(data,selected_pages=pages,**context)

    def test_evidence_truncation_is_not_erased_by_other_pages(self):
        old={"sha256":"a"*64,"pages_reported":2,"pages_examined":1,"evidence_truncated":True,
             "page_states":[{"page":1,"status":"read","attempts":1}],"indicators":[]}
        new={"sha256":"a"*64,"pages_reported":2,"page_states":[{"page":2,"status":"read","attempts":1}],
             "indicators":[],"binary_persisted":False}
        result=merge(old,new)
        self.assertEqual(result["pages_read"],2)
        self.assertTrue(result["truncated"])

    def test_subprocess_reader_works_outside_repository_cwd(self):
        import os
        saved=Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                os.chdir(folder)
                result=inspect_pdf(fixtures.pdf(["Datos NIT 900317964-1 fuente documental"]),
                    source="ps88-5e3v",process_ref=fixtures.REF,process_url=fixtures.PROCESS,
                    document_url="https://www.contratos.gov.co/archivos/test.pdf")
                self.assertEqual(result["pages_read"],1)
        finally:os.chdir(saved)


if __name__=="__main__":unittest.main()
