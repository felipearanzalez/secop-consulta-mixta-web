"""Integridad documental, reanudacion y conciliacion sin tocar la web publicada."""
from __future__ import annotations
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit

from reportlab.pdfgen.canvas import Canvas
from index28.persistence import DocumentStore
from index28.pipeline import run_process,priority
from index28.evidence import parse_pdf,inspect_pdf
from index28.composition import memberships
from index28.secop_i_documents import resolve_link,valid_pdf_url
from index28.reconciliation import reconcile,reconcile_export,contract_key

REF="26-11-14749233"
PROCESS="https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia="+REF
BDOS="CO1.BDOS.8263083"


def pdf(lines=None, pages=1):
    b=io.BytesIO();c=Canvas(b)
    for p in range(pages):
        for n,line in enumerate(lines or []):
            c.drawString(35,780-18*n,line)
        c.showPage()
    c.save();return b.getvalue()


def document(doc_id="123",name="Informe de evaluacion.pdf",modified="2026-10-13",url=None):
    return {"id":doc_id,"name":name,"description":name,"modified_at":modified,
            "source":"ps88-5e3v","download_url_published":url}


def snapshot(docs):
    return {"platform":"SECOP I","reference":REF,"process_url":PROCESS,
            "contract_records":[],"proponent_records":[],"document_metadata":docs,
            "coverage":[{"dataset":"ps88-5e3v","status":"ok","truncated":False}],
            "complete_in_requested_sources":True}


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.pg_url=os.getenv("SECOP_TEST_DATABASE_URL")
        if self.pg_url:
            if urlsplit(self.pg_url).hostname not in {"localhost","127.0.0.1"}:
                raise ValueError("Las pruebas SQL solo aceptan bases locales aisladas")
            self.url=self.pg_url
            self.namespace="t_"+uuid.uuid4().hex
            s=DocumentStore(self.url)
            try:
                s.execute('CREATE SCHEMA '+self.namespace);s.con.commit()
            finally:s.close()
        else:
            self.url="sqlite:///"+str(Path(self.temp.name)/"index.db")
        self.store=self.open()

    def open(self):
        s=DocumentStore(self.url)
        if self.pg_url:
            s.execute('SET search_path TO '+self.namespace);s.con.commit()
        s.create_document_schema()
        return s

    def tearDown(self):
        self.store.close()
        if self.pg_url:
            s=DocumentStore(self.url)
            try:s.execute('DROP SCHEMA '+self.namespace+' CASCADE');s.con.commit()
            finally:s.close()
        self.temp.cleanup()

    def test_resume_after_restart_and_no_duplicate_observation(self):
        url="https://www.contratos.gov.co/archivos/PROCESO_"+REF+"_123.pdf"
        doc=document(url=url)
        src=snapshot([doc]);calls=[]
        data=pdf(["CONSORCIO PRUEBA","Integrantes - participacion",
                  "EMPRESA UNO S.A.S. | NIT 900.317.964-1 | 40 %",
                  "EMPRESA DOS S.A.S. | NIT 800.143.586-1 | 60 %"])
        def download(u,ref,ident):calls.append(u);return data
        first=run_process(self.store,"SECOP I",REF,inventory=src,download_i=download)
        self.assertEqual(first["attempted_in_batch"],1)
        self.assertTrue(first["complete_in_requested_sources"])
        self.store.close();self.store=self.open()
        second=run_process(self.store,"SECOP I",REF,inventory=src,download_i=download)
        self.assertEqual(second["attempted_in_batch"],0)
        self.assertEqual(second["previous_results_reused"],1)
        self.assertEqual(len(calls),1)
        result=self.store.candidates("900317964-1")
        compositions=[r for r in result["observations"] if r["evidence_kind"]=="composition_candidate"]
        self.assertEqual(len(compositions),1)
        self.assertEqual(compositions[0]["observation"]["share_percent"],"40")
        self.assertEqual(result["verified_contracts_from_observations"],0)
        self.assertFalse(self.store.result(first["jobs"][0]["job_key"])["binary_persisted"])

    def test_changed_document_keeps_previous_result(self):
        key=self.store.enqueue("SECOP I",REF,document(),0)
        job=self.store.claim(key)
        result=parse_pdf(pdf(["Identificacion NIT 900317964-1"]),source="ps88-5e3v",process_ref=REF,
                         process_url=PROCESS,document_url="https://www.contratos.gov.co/archivos/PROCESO_"+REF+"_123.pdf")
        self.store.finish(key,job["lease_token"],result)
        modified=self.store.enqueue("SECOP I",REF,document(modified="2026-10-14"),0)
        self.assertNotEqual(key,modified)
        self.assertEqual(self.store.result(key)["sha256"],result["sha256"])
        self.assertIsNone(self.store.result(modified))

    def test_two_workers_and_expired_lease(self):
        key=self.store.enqueue("SECOP I",REF,document(),0)
        original=self.store.claim(key,now=1000)
        self.store.con.commit()
        other=self.open()
        try:
            self.assertIsNone(other.claim(key,now=1100))
            replacement=other.claim(key,now=1200)
            other.con.commit()
            self.assertNotEqual(original["lease_token"],replacement["lease_token"])
            result={"sha256":"a"*64,"binary_persisted":False,"indicators":[]}
            with self.assertRaisesRegex(ValueError,"no pertenece"):
                self.store.finish(key,original["lease_token"],result)
            other.finish(key,replacement["lease_token"],result)
            self.assertEqual(other.job(key)["status"],"parsed")
            other.con.commit()
        finally:other.close()

    def test_atomic_rollback_does_not_complete_invalid_result(self):
        key=self.store.enqueue("SECOP I",REF,document(),0)
        job=self.store.claim(key)
        broken={"sha256":"b"*64,"binary_persisted":False,"indicators":[{"nit":"900317964","page":0}]}
        with self.assertRaisesRegex(ValueError,"Pagina"):
            self.store.finish(key,job["lease_token"],broken)
        self.assertEqual(self.store.job(key)["status"],"working")
        self.assertIsNone(self.store.result(key))

    def test_first_document_survives_failure_in_next_document(self):
        docs=[document("123",url="https://www.contratos.gov.co/archivos/PROCESO_"+REF+"_123.pdf"),
              document("124",url="https://www.contratos.gov.co/archivos/PROCESO_"+REF+"_124.pdf")]
        def download(url,ref,ident):
            if ident=="124":raise HTTPError(url,429,"too many",{},None)
            return pdf(["Fuente documental NIT 900317964-1"])
        report=run_process(self.store,"SECOP I",REF,inventory=snapshot(docs),download_i=download)
        self.assertEqual([j["status"] for j in report["jobs"]],["parsed","failed"])
        self.assertFalse(report["complete_in_requested_sources"])
        self.assertEqual(self.store.candidates("900317964")["count_observations"],1)

    def test_403_records_block_without_claiming_zero_contracts(self):
        def denied(url,ref):raise HTTPError(url,403,"Forbidden",{},None)
        report=run_process(self.store,"SECOP I",REF,inventory=snapshot([document()]),html_i=denied)
        self.assertEqual(report["jobs"][0]["status"],"blocked")
        self.assertEqual(report["jobs"][0]["last_error"],"http_403")
        self.assertFalse(report["complete_in_requested_sources"])
        self.assertEqual(report["verified_member_contracts_created"],0)
        self.assertEqual(report["remaining_documents"],1)

    def test_scanned_document_stays_partial(self):
        key=self.store.enqueue("SECOP I",REF,document(),0)
        job=self.store.claim(key)
        result=parse_pdf(pdf(),source="ps88-5e3v",process_ref=REF,process_url=PROCESS,
                         document_url="https://www.contratos.gov.co/archivos/PROCESO_"+REF+"_123.pdf")
        self.assertEqual(result["unreadable_pages"],[1])
        self.store.finish(key,job["lease_token"],result)
        self.assertEqual(self.store.job(key)["status"],"partial")

    def test_old_verified_index_is_preserved(self):
        self.store.create_schema()
        cases=Path(__file__).resolve().parents[1]/"index27/verified_cases.json"
        self.store.import_cases(cases)
        before=self.store.find("800143586-1")["contracts"]
        self.store.save_inventory(snapshot([document()]))
        self.store.enqueue("SECOP I",REF,document(),0)
        after=self.store.find("800143586-1")["contracts"]
        self.assertEqual(before,after)
        self.assertEqual(len(after),1)

    def test_single_batch_continues_after_already_parsed_jobs(self):
        docs=[document(str(i),url=f"https://www.contratos.gov.co/archivos/PROCESO_{REF}_{i}.pdf") for i in range(120,123)]
        calls=[]
        def downloader(url,ref,ident):calls.append(ident);return pdf(["Datos documentales NIT 900317964-1"])
        first=run_process(self.store,"SECOP I",REF,inventory=snapshot(docs),download_i=downloader,max_documents=1)
        self.assertEqual(first["remaining_documents"],2)
        second=run_process(self.store,"SECOP I",REF,inventory=snapshot(docs),download_i=downloader,max_documents=1)
        self.assertEqual(second["remaining_documents"],1)
        self.assertEqual(calls,["120","121"])


class CompositionAndLinkTests(unittest.TestCase):
    def test_prioritize_evaluation_and_policies_before_contract(self):
        names=["Contrato.pdf","Poliza de consorcio.pdf","Informe evaluacion.pdf","CDP.pdf"]
        self.assertEqual([priority({"name":name}) for name in names],[2,0,0,4])

    def test_no_guessed_download_or_other_process_link(self):
        link=f"https://www.contratos.gov.co/archivos/PROCESO_{REF}_123.pdf"
        self.assertEqual(resolve_link(f'<a href="{link}">Evaluacion</a>'.encode(),PROCESS,REF,"123"),link)
        self.assertIsNone(resolve_link(b'<a href="http://20.96.127.85/descarga/123">Archivo</a>',PROCESS,REF,"123"))
        self.assertFalse(valid_pdf_url(link,"21-4-12343945","123"))
        self.assertFalse(valid_pdf_url(link,REF,"12"))
        self.assertIsNone(resolve_link(f'<a href="{link}">A</a><a href="{link.replace("/archivos/","/otro/")}">B</a>'.encode(),PROCESS,REF,"123"))

    def test_representative_and_insurance_percentage_excluded(self):
        lines="""CONSORCIO PRUEBA
Integrantes y participacion
EMPRESA UNO | NIT 900.317.964-1 | 40 %
REPRESENTANTE LEGAL: MARIO | CC 1143330527 | 60 %
ASEGURADORA | NIT 800.143.586-1 | AMPARO 10 %
EMPRESA DOS | NIT 901.601.837-5
"""
        rows=memberships(lines,2)
        self.assertEqual([r["id_base"] for r in rows],["900317964","901601837"])
        self.assertEqual(rows[0]["share_percent"],"40")
        self.assertIsNone(rows[1]["share_percent"])
        self.assertTrue(all(not r["contract_attribution"] for r in rows))

    def test_content_order_paragraph_and_same_page(self):
        text="""NOMBRE OFERENTE: CONSORCIO PRUEBA REPRESENTANTE LEGAL: PERSONA CC. 1143330527
INTEGRADA POR: 1. EMPRESA UNO S.A.S. NIT. 901.885.583-8 PARTICIPACION: 50% 2. EMPRESA DOS S.A.S. NIT. 901.885.558-3 PARTICIPACION: 50% 1. INFORME DE EVALUACION
"""
        rows=memberships(text,2)
        self.assertEqual([r["id_base"] for r in rows],["901885583","901885558"])
        self.assertTrue(all(r["share_percent"]=="50" for r in rows))
        self.assertEqual(memberships("INTEGRADA POR: EMPRESA NIT 900317964-1 PARTICIPACION 50%",3),[])

    def test_page_limit_reports_actual_count_and_isolated_parser(self):
        payload=pdf(["Documental NIT 900317964-1"],pages=2)
        context=dict(source="ps88-5e3v",process_ref=REF,process_url=PROCESS,
                     document_url=f"https://www.contratos.gov.co/archivos/PROCESO_{REF}_123.pdf")
        result=inspect_pdf(payload,max_pages=1,**context)
        self.assertEqual(result["pages_examined"],1)
        self.assertEqual(result["pages_reported"],2)
        self.assertTrue(result["truncated"])
        self.assertFalse(result["binary_persisted"])


class ReconciliationTests(unittest.TestCase):
    def test_no_baseline_loss_or_overwrite_on_conflicting_and_partial_source(self):
        before=[{"platform":"II","contractId":"CO1.PCCNTR.5365625","state":"Suspendido",
                 "start":"2024-04-01","end":"2024-11-28","value":"5947664432","group":{"percent":"90"}},
                {"platform":"II","contractId":"CO1.PCCNTR.5151026","state":"Suspendido","end":"2026-09-20"}]
        original=copy.deepcopy(before)
        key="II|CO1.PCCNTR.5365625"
        new=[{**before[0],"association_verified":True,"state":"En ejecucion",
              "reviewed_by":"revisor_prueba","reviewed_at":"2026-10-13T22:00:00+00:00",
              "reviewed_evidence":[{"kind":kind,"contract_key":key,"page":1,"sha256":"d"*64,
                   "url":"https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592"}
                 for kind in ["contrato_firmado","composicion_plural"]]}]
        out=reconcile(before,new,coverage=[{"status":"partial"}])
        self.assertEqual(before,original)
        self.assertEqual(out["baseline_records_preserved"],2)
        self.assertEqual(out["distinct_contract_records"],2)
        self.assertEqual(out["records"][0]["record"]["state"],"Suspendido")
        self.assertEqual(out["conflict_count"],1)
        self.assertFalse(out["coverage_complete"])

    def test_pending_member_cannot_create_contract(self):
        hint={"platform":"II","contractId":"CO1.PCCNTR.5365625","nit":"900317964","association_verified":False}
        out=reconcile([], [hint],coverage=[{"status":"ok"}])
        self.assertEqual(out["records"],[])
        self.assertEqual(out["pending_evidence"],[hint])
        self.assertFalse(out["asserts_absence_of_contracts"])

    def test_unsubstantiated_verified_flag_is_not_accepted(self):
        fake={"platform":"II","contractId":"CO1.PCCNTR.5365625","association_verified":True}
        out=reconcile([], [fake],coverage=[{"status":"ok"}])
        self.assertEqual(out["new_verified_records"],0)
        self.assertEqual(out["pending_evidence"],[fake])

    def test_distinct_contracts_in_one_secop_i_process_stay_distinct(self):
        a={"platform":"I","constancia":REF,"reference":"001-2026","contractorId":"900317964-1"}
        b={**a,"reference":"002-2026"}
        self.assertNotEqual(contract_key(a),contract_key(b))
        out=reconcile([a,b,a],[],coverage=[])
        self.assertEqual(out["distinct_contract_records"],2)
        self.assertEqual(out["baseline_records_preserved"],3)
        self.assertEqual(len(out["records"][0]["baseline_variants"]),1)

    def test_export_keeps_report_categories_and_optional_croma_exactly(self):
        baseline={"identity":{"raw":"900317964-1"},"report":{"execution":[],"contracts":[
           {"platform":"II","contractId":"CO1.PCCNTR.5365625","state":"Suspendido","modality":"plural"}],
           "tasks":[{"status":"ok"}],"pluralParticipation":[{"percent":"90"}]},
           "croma":{"enabled":True,"records":[{"number":"1554"}]}}
        out=reconcile_export(baseline,{"records":[],"coverage":[{"status":"partial"}]})
        self.assertEqual(out["report"],baseline["report"])
        self.assertEqual(out["croma"],baseline["croma"])
        self.assertFalse(out["documentary_reconciliation"]["coverage_complete"])


if __name__=="__main__":unittest.main()
