"""Regimen especial sin adjudicatario, revision a corte y conservacion de resultados."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from index28.review import ReviewStore
from index28.composition import memberships
from index28.evidence import parse_pdf,table_nit_mentions
from index28.special_discovery import seed_special,discovery_url
from index28.portal import catalogue_portal,valid_portal_document
from index28.pipeline import execute_job
from index28.api import build_handler
import test_document_pipeline as fixtures

REF="PAF-INVIAS-O-082-2023"
PORTAL="https://www.findeter.gov.co/convocatorias/"+REF.lower()
PDF="https://www.findeter.gov.co/system/files/convocatorias/"+REF+"/informe_definitivo_de_verificacion_de_requisitos_habilitantes.pdf"
CLAUSE="""CONSORCIO MEJORAMIENTO SUROESTE, identificado con NIT 901.918.750-5, debidamente constituido conforme a la normatividad colombiana, integrada por: INGENIERIA TRANSPORTE Y MAQUINARIA S.A.S NIT 900.102.268-1 (Con 90% de participación) y MINOICA INGENIERIA S.A.S NIT 901.848.505-6 (Con 10% de participación) y quien para los mismos efectos se denominará EL CONTRATISTA. El supervisor verifica las obligaciones."""


def snapshot():
    return {"identity":{"raw":"900102268-1"},"at":"2026-10-13T22:00:00Z",
      "report":{"execution":[],"contracts":[{"platform":"II","contractId":"CO1.PCCNTR.6644739","key":"II|6644739","reference":"3460-2024","state":"Suspendido","start":"2024-10-25","end":"2026-11-30","value":"123","sourceRow":{"fecha_de_firma":"2024-10-01"}}],"tasks":[{"status":"partial","label":"Una fuente pendiente","count":1}]},
      "extended":{"awards":[{"portfolio":"CO1.BDOS.9231141","reference":"LP-DEO-SVR-063-2025","awardDate":"2026-07-07","group":"CONSORCIO INMAHA"}]},
      "croma":{"status":"ok","direct":{"records":[{"reference":"Croma adicional"}]}}}


class ReviewTests(unittest.TestCase):
    setUp=fixtures.PersistenceTests.setUp
    tearDown=fixtures.PersistenceTests.tearDown
    def open(self):
        store=ReviewStore(self.url)
        if self.pg_url:
            store.execute('SET search_path TO '+self.namespace);store.con.commit()
        store.create_review_schema();return store

    def test_suspended_retained_and_past_cutoff_not_reconstructed(self):
        self.store.save_snapshot(snapshot());view=self.store.view("900102268-1","2026-09-08")
        self.assertEqual(view["counts"]["suspended"],1)
        self.assertEqual(view["contracts"][0]["state"],"Suspendido")
        self.assertFalse(view["contracts"][0]["cutoff_review"]["state_as_of_cutoff_verified"])
        self.assertFalse(view["awards"][0]["contract_verified"])

    def test_dates_annotate_without_deleting_and_croma_original_preserved(self):
        source=snapshot();source["report"]["contracts"][0]["sourceRow"]["fecha_de_firma"]="2026-09-09"
        before=copy.deepcopy(source);self.store.save_snapshot(source)
        exported=self.store.export("900102268","2026-09-08")
        self.assertEqual(exported["original_210"],before)
        self.assertTrue(exported["review"]["contracts"][0]["cutoff_review"]["signature_after_cutoff"])
        self.assertEqual(len(exported["review"]["contracts"]),1)

    def test_evidence_without_snapshot_is_not_empty_complete_search(self):
        doc={"document_id":"123","filename":"Acta de inicio.pdf","source":"dmgg-8hin","download_url_published":"https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=123"}
        key=self.store.enqueue("SECOP II",fixtures.BDOS,doc,0)
        result=execute_job(self.store,key,download_ii=lambda url:fixtures.pdf(CLAUSE.splitlines()),parser=parse_pdf)
        self.assertEqual(result["status"],"parsed")
        view=self.store.view("900102268-1","2026-09-08")
        self.assertFalse(view["snapshot_available"])
        self.assertFalse(view["asserts_absence_of_contracts"])
        self.assertEqual(view["counts"]["documentary_files"],1)
        self.assertFalse(view["documentary_evidence"][0]["contract_verified"])

    def test_invalid_dates_and_snapshot_identity_rejected(self):
        for cutoff in ["2026-02-30","2026-9-8","today"]:
            with self.assertRaises(ValueError):self.store.view("900102268",cutoff)
        invalid=snapshot();invalid["identity"]["raw"]="not-a-nit"
        with self.assertRaises(ValueError):self.store.save_snapshot(invalid)

    def test_latest_snapshot_selected_by_utc_time_not_offset_string(self):
        older=snapshot();older["at"]="2026-10-13T23:00:00+02:00"
        newer=snapshot();newer["at"]="2026-10-13T20:00:00-05:00"
        self.store.save_snapshot(newer);self.store.save_snapshot(older)
        self.assertEqual(self.store.snapshot("900102268")["payload"]["at"],newer["at"])

    def test_portal_evidence_uses_same_queue_and_restarts_without_duplicate(self):
        html=f'<h1>{REF}</h1><a href="/system/files/internas/plan.pdf">Plan</a><table><tr><td>Documentos</td><td><a href="{PDF}">informe_definitivo_de_verificacion_de_requisitos_habilitantes.pdf</a></td></tr></table>'.encode()
        first=catalogue_portal(self.store,REF,fetcher=lambda *a,**kw:(html,"text/html"))
        self.assertEqual(first["documents_listed"],1)
        self.assertEqual(first["coverage"][0]["status"],"ok")
        key=first["job_keys"][0]
        self.assertEqual(self.store.job(key)["document"]["kind"],"evaluacion")
        text="FORMATO EVALUACION FINANCIERA\nINFORMACION PROPONENTE\nIntegrante 1 Nit 1 Part (%) 1\n900102268-1 40% Nacional"
        execute_job(self.store,key,download_portal=lambda *args:fixtures.pdf(text.splitlines()),parser=parse_pdf)
        self.store.close();self.store=self.open()
        second=catalogue_portal(self.store,REF,fetcher=lambda *a,**kw:(html,"text/html"))
        self.assertEqual(second["job_keys"],[key])
        view=self.store.view("900102268","2026-09-08")
        self.assertEqual(view["counts"]["documentary_files"],1)
        self.assertEqual(view["documentary_evidence"][0]["platform"],"FINDETER")

    def test_discovery_without_awardee_and_partial_inventory_cannot_skip(self):
        references=["CO1.BDOS.1000","CO1.BDOS.2000"]
        def fetch(url):return [{"id_del_portafolio":x} for x in references]
        def inventory(ref,**kw):
            return {"platform":"SECOP II","portfolio":ref,"document_metadata":[],"contract_records":[],"complete_in_requested_sources":ref==references[0]}
        result=seed_special(self.store,fetch=fetch,inventory_fn=inventory,limit=2)
        self.assertEqual(result["status"],"partial")
        self.assertEqual(result["cursor"],references[0])
        self.assertNotIn("adjudicado",discovery_url())
        self.assertNotIn("nit",discovery_url())

    def test_review_api_and_static_preview_no_write_or_path_traversal(self):
        self.store.save_snapshot(snapshot())
        server_url=self.url
        if self.pg_url:
            server_url+=('&' if '?' in server_url else '?')+urlencode({'options':'-csearch_path='+self.namespace})
        server=ThreadingHTTPServer(('127.0.0.1',0),build_handler(server_url))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_address[1]}'
        try:
            with urlopen(base+'/api/review/search?nit=900102268&cutoff=2026-09-08') as r:
                self.assertEqual(json.load(r)["counts"]["suspended"],1)
            with urlopen(base+'/review/') as r:
                self.assertIn(b'Content-Security-Policy',str(r.headers).encode())
                self.assertIn(b'Revisi',r.read())
            for route in ['/review/../index27/verified_cases.json','/api/review/search?nit=900102268&cutoff=2026-09-08&url=https://evil.test']:
                with self.assertRaises(HTTPError):urlopen(base+route)
        finally:server.shutdown();server.server_close();thread.join(timeout=2)


class ExtractionTests(unittest.TestCase):
    def test_contract_clause_keeps_two_members_not_representative_or_supervisor(self):
        # El PDF real corta la denominacion del consorcio y el NIT en dos lineas.
        wrapped=CLAUSE.replace('CONSORCIO MEJORAMIENTO','CONSORCIO\nMEJORAMIENTO').replace('NIT 900','NIT\n900')
        rows=memberships(wrapped,1)
        self.assertEqual([(x["id_base"],x["share_percent"]) for x in rows],[("900102268","90"),("901848505","10")])
        self.assertTrue(all(x["group"]=="CONSORCIO MEJORAMIENTO SUROESTE" for x in rows))
        self.assertEqual(rows[1]["member_name"],"MINOICA INGENIERIA S.A.S")
        self.assertTrue(all(not x["contract_attribution"] for x in rows))

    def test_bare_table_identification_requires_form_headers(self):
        ident="900102268-1"
        self.assertEqual(table_nit_mentions('Oferta economica '+ident),[])
        rows=table_nit_mentions('INFORMACION PROPONENTE Integrante 2 Nit 2 Part (%) 2 '+ident+' 40% Nacional')
        self.assertEqual([x["nit"] for x in rows],["900102268"])
        self.assertNotIn("share_percent",rows[0])

    def test_portal_rejects_different_process_http_and_encoded_traversal(self):
        self.assertTrue(valid_portal_document(PDF,REF))
        for url in [PDF.replace('https:','http:'),PDF.replace(REF,'PAF-INVIAS-O-081-2023'),PDF.replace('/informe','/%2e%2e/informe'),PDF+'?url=https://evil.test']:
            self.assertFalse(valid_portal_document(url,REF))


if __name__=='__main__':unittest.main()
