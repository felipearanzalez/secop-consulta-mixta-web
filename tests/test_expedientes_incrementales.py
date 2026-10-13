from __future__ import annotations

import io
import unittest
from urllib.parse import parse_qs, urlsplit

from index28.socrata import exact_url, scan_exact
from index28.expediente_secop_i import expediente as expediente_i
from index28.regimen_especial_secop2 import (
    expediente as expediente_ii, document_kind, published_document_link,
    special_modality,
)
from index28.evidence import nit_mentions, parse_pdf
from index28.checkpoints import ensure_schema, read, record
from index27.store import Store


class SocrataReferenceTests(unittest.TestCase):
    def test_exact_filters_only(self):
        for dataset, reference, field in (("f789-7hwg", "21-4-12343945", "numero_de_constancia"),
                                          ("dmgg-8hin", "CO1.BDOS.8263083", "proceso")):
            q=parse_qs(urlsplit(exact_url(dataset,reference,limit=75,offset=4)).query)
            self.assertEqual(q["$where"],[f"{field}='{reference}'"])
            self.assertEqual(q["$limit"],["75"])
        for ref in ("abc", "CO1.BDOS.8263083' OR 1=1", "1;DROP TABLE", "https://localhost/"):
            with self.assertRaises(ValueError):
                exact_url("dmgg-8hin",ref)
        with self.assertRaises(ValueError):
            exact_url("fake-dataset", "21-4-12343945")
        with self.assertRaises(ValueError):
            exact_url("f789-7hwg", "CO1.BDOS.8263083")

    def test_lost_page_is_partial_not_zero(self):
        seen=[]
        def fetch(url):
            q=parse_qs(urlsplit(url).query)
            seen.append(int(q["$offset"][0]))
            if int(q["$offset"][0])==0:
                return [{"numero_de_constancia":"21-4-12343945","i":1},{"numero_de_constancia":"21-4-12343945","i":2}]
            raise ConnectionError("HTTP 429")
        records, status=scan_exact("f789-7hwg", "21-4-12343945",fetch,page_size=2,max_pages=3)
        self.assertEqual(len(records),2)
        self.assertEqual(status["status"],"partial")
        self.assertIn("429",status["error"])
        self.assertEqual(seen,[0,2])

    def test_full_page_probes_exhaustiveness(self):
        def fetch(url):
            q=parse_qs(urlsplit(url).query)
            if q["$offset"]==["2"]:return []
            return [{"i":1},{"i":2}]
        rows,state=scan_exact("f789-7hwg","21-4-12343945",fetch,page_size=2,max_pages=1)
        self.assertEqual(len(rows),2)
        self.assertEqual(state["status"],"ok")


class SecopITests(unittest.TestCase):
    REF="21-4-12343945"
    def fake(self,url):
        dataset=urlsplit(url).path.rsplit("/",1)[-1].removesuffix(".json")
        if dataset=="f789-7hwg":
            return [{"uid":"21-4-12343945-11433737","numero_de_constancia":self.REF,
                     "numero_de_contrato":"CTO 129 - 2021","estado_del_proceso":"Liquidado",
                     "nom_razon_social_contratista":"IES INGENIEROS S.A.S.",
                     "identificacion_del_contratista":"900317964",
                     "fecha_de_firma_del_contrato":"2021-09-16T00:00:00.000",
                     "fecha_ini_ejec_contrato":"2021-09-16T00:00:00.000",
                     "fecha_fin_ejec_contrato":"2023-05-13T00:00:00.000",
                     "valor_contrato_con_adiciones":"2420432632","nombre_entidad":"AGUAS DE BOGOTA"}]
        if dataset=="qddk-cgux":return []
        if dataset=="tauh-5jvn":return [{"id_proceso":self.REF,"proponente":"IES INGENIEROS S.A.S.","adjudicado":"SI","numero_contrato":"CTO 129 - 2021"}]
        if dataset=="ps88-5e3v":return [{"identificador":"103352199","numero_de_constancia":self.REF,
                                          "nombrearchivo":"ADIC_PROCESO_21-4-12343945_211001399_103352199.pdf",
                                          "descripcion":"OTROSI 4 CTO 129 - 2021","ruta_descarga":"http://20.96.127.85/descarga/103352199"}]
        if dataset=="8kpz-m6cc":return []
        raise AssertionError(dataset)

    def test_known_real_secop_i_process(self):
        r=expediente_i(self.REF,fetch=self.fake)
        self.assertTrue(r["complete_in_requested_sources"])
        self.assertEqual(len(r["coverage"]),5)
        self.assertEqual(len(r["contract_records"]),1)
        self.assertEqual(r["contract_records"][0]["signature_date_reported"][:10],"2021-09-16")
        self.assertEqual(r["contract_records"][0]["value_reported"],"2420432632")
        self.assertEqual(len(r["document_metadata"]),1)
        self.assertFalse(r["document_metadata"][0]["safe_public_download_verified"])
        self.assertEqual(r["document_texts_examined"],0)
        self.assertEqual(r["membership_confirmed_by_documents"],0)

    def test_incomplete_sources_visible(self):
        def fetch(url):
            if "tauh-5jvn" in url: raise OSError("proveedores inaccesibles")
            return self.fake(url)
        r=expediente_i(self.REF,fetch=fetch)
        self.assertFalse(r["complete_in_requested_sources"])
        self.assertIn("failed",[c["status"] for c in r["coverage"]])
        self.assertEqual(len(r["contract_records"]),1)

    def test_reject_cross_process_return(self):
        def mixed(url):
            if "ps88-5e3v" in url:
                return [{"numero_de_constancia":"17-1-169268","identificador":"11"}]
            return self.fake(url)
        r=expediente_i(self.REF,fetch=mixed)
        self.assertFalse(r["complete_in_requested_sources"])
        self.assertEqual(r["document_metadata"],[])


class RegimenSpecialTests(unittest.TestCase):
    BDO="CO1.BDOS.8263083"
    DOC_BASE="https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId={}&InCommunity=False&InPaymentGateway=False&DocUniqueIdentifier="

    def test_safe_document_links_and_classification(self):
        r={"id_documento":"625136592","url_descarga_documento":{"url":self.DOC_BASE.format("625136592")}}
        self.assertEqual(published_document_link(r),self.DOC_BASE.format("625136592"))
        self.assertIsNone(published_document_link({"id_documento":"625136592","url_descarga_documento":{"url":self.DOC_BASE.format("625136599")}}))
        self.assertIsNone(published_document_link({"id_documento":"625136592","url_descarga_documento":"https://community.secop.gov.co.evil.com/hi?DocumentId=625136592"}))
        self.assertIsNone(published_document_link({"id_documento":"625136592","url_descarga_documento":"http://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592"}))
        self.assertTrue(special_modality("Contratación régimen especial"))
        self.assertFalse(special_modality("Contratación directa"))
        self.assertEqual(document_kind("CONTRATO 280.pdf"),"contrato_posible")
        self.assertEqual(document_kind("ACTA DE INICIO 280.pdf"),"inicio")
        self.assertEqual(document_kind("GARANTÍA DE CONSORCIO.pdf"),"posible_composicion")

    def fake(self,url):
        dataset=urlsplit(url).path.rsplit("/",1)[-1].removesuffix(".json")
        if dataset=="jbjy-vk9h":return []  # No contract in structured source
        if dataset=="p6dx-8zbt":return []  # No award structured
        if dataset=="dmgg-8hin":
            return [{"proceso":self.BDO,"id_documento":number,
                     "nombre_archivo":name,"entidad":"ESE HOSPITAL SAN ANTONIO DE CHIA",
                     "url_descarga_documento":{"url":self.DOC_BASE.format(number)},
                     "fecha_carga":"2025-06-12T00:00:00.000"} for number,name in [
                        ("625136592","CONTRATO 280.pdf"),("625136599","ACTA DE INICIO 280.pdf"),
                        ("625136600","ADJUDICACION 280.pdf")]]
        raise AssertionError(dataset)

    def test_docs_survive_missing_structured_contract(self):
        out=expediente_ii(self.BDO,fetch=self.fake)
        self.assertTrue(out["complete_in_requested_sources"])
        self.assertEqual(len(out["document_metadata"]),3)
        self.assertEqual(len(out["contract_records"]),0)
        self.assertFalse(out["is_special_regime_reported"])
        self.assertEqual(out["document_texts_examined"],0)
        self.assertEqual(out["member_contract_relations_verified"],0)
        self.assertTrue(all(not x["access_confirmed"] for x in out["document_metadata"]))
        self.assertEqual(out["document_metadata"][0]["kind"],"contrato_posible")

    def test_explicit_special_modality_does_not_prove_execution(self):
        def fake(url):
            dataset=urlsplit(url).path.rsplit("/",1)[-1].removesuffix(".json")
            if dataset=="jbjy-vk9h":
                return [{"proceso_de_compra":self.BDO,"id_contrato":"CO1.PCCNTR.1234567",
                         "estado_contrato":"Suspendido","modalidad_de_contratacion":"Régimen Especial",
                         "fecha_de_inicio_del_contrato":"2025-05-01", "fecha_de_fin_del_contrato":"2027-05-01"}]
            if dataset=="p6dx-8zbt":return [{"id_del_portafolio":self.BDO,"modalidad_de_contratacion":"Régimen Especial"}]
            return []
        r=expediente_ii(self.BDO,fetch=fake)
        self.assertTrue(r["is_special_regime_reported"])
        self.assertEqual(r["contract_records"][0]["status_reported"],"Suspendido")
        self.assertEqual(r["contract_records"][0]["end_date_reported"],"2027-05-01")
        self.assertNotIn("execution_verified",r["contract_records"][0])

    def test_draft_not_promoted_to_contract(self):
        def fake(url):
            dataset=urlsplit(url).path.rsplit("/",1)[-1].removesuffix(".json")
            if dataset=="jbjy-vk9h":return [{"proceso_de_compra":self.BDO,"id_contrato":"CO1.PCCNTR.1234567","estado_contrato":"Pendiente de firma"}]
            return []
        r=expediente_ii(self.BDO,fetch=fake)
        self.assertEqual(r["contract_records"],[])


class CheckpointsTests(unittest.TestCase):
    def test_never_advance_after_partial(self):
        store=Store("sqlite:///:memory:")
        try:
            ensure_schema(store)
            completed=record(store,"dmgg-8hin","CO1.BDOS.8263083",status="ok",count=200,cursor="offset:200")
            self.assertEqual(completed["cursor"],"offset:200")
            partial=record(store,"dmgg-8hin","CO1.BDOS.8263083",status="partial",count=100,cursor="offset:300",error="HTTP429")
            self.assertEqual(partial["cursor"],"offset:200")
            self.assertEqual(partial["last_success_at"],completed["last_success_at"])
            self.assertEqual(partial["status"],"partial")
            with self.assertRaises(ValueError):
                record(store,"otro-dataset","CO1.BDOS.8263083",status="ok",count=1,cursor="1")
        finally:
            store.close()


class EvidenceTests(unittest.TestCase):
    def test_nit_mentions_are_indicia_only(self):
        text="Identificado NIT 900317964-1. Cuenta bancaria 111222333. Tambien N.I.T. 800.143.586-1."
        rows=nit_mentions(text)
        self.assertEqual([x["nit"] for x in rows],["900317964","800143586"])
        self.assertTrue(all(x["verification_status"]=="indicio_no_verificado" for x in rows))

    def test_pdf_extract_memory_only(self):
        try:
            from reportlab.pdfgen.canvas import Canvas
        except ImportError:
            self.skipTest("reportlab not installed")
        b=io.BytesIO(); c=Canvas(b); c.drawString(50,700,"Empresa registrada NIT 900317964-1 - documento no prueba contrato")
        c.showPage();c.save()
        parsed=parse_pdf(b.getvalue(),source="dmgg-8hin",process_ref="CO1.BDOS.8263083",
                         process_url="https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.1116225",
                         document_url="https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592")
        self.assertEqual(parsed["pages_examined"],1)
        self.assertEqual(parsed["indicators"][0]["nit"],"900317964")
        self.assertFalse(parsed["contract_verified"])
        self.assertFalse(parsed["binary_persisted"])


if __name__=="__main__":
    unittest.main()

class WorkerTests(unittest.TestCase):
    def test_scanned_pdf_does_not_mark_legacy_inventory_complete(self):
        from index28.document_worker import inspect_portfolio
        from reportlab.pdfgen.canvas import Canvas
        b=io.BytesIO();c=Canvas(b);c.showPage();c.save()
        url="https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592"
        def source(addr):
            if "dmgg-8hin" in addr:
                return [{"proceso":"CO1.BDOS.8263083","id_documento":"625136592",
                         "nombre_archivo":"CONTRATO 280.pdf","url_descarga_documento":{"url":url}}]
            return []
        result=inspect_portfolio("CO1.BDOS.8263083",fetch=source,download=lambda uri:b.getvalue())
        self.assertEqual(result["documents_inspected"][0]["status"],"partial")
        self.assertEqual(result["documents_inspected"][0]["unreadable_pages"],[1])
        self.assertFalse(result["coverage_complete"])

    def test_safe_download_refuses_bad_domains(self):
        from index28.document_worker import valid_document_uri,read_pdf_https
        self.assertFalse(valid_document_uri("https://user:password@community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=10"))
        self.assertFalse(valid_document_uri("https://evil.test/doc.pdf"))
        self.assertTrue(valid_document_uri("https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592"))
        with self.assertRaises(ValueError):
            read_pdf_https("http://20.96.127.85/descarga/12345")

    def test_worker_extracts_only_indicia_without_persisting_pdf(self):
        from index28.document_worker import inspect_portfolio
        from reportlab.pdfgen.canvas import Canvas
        b=io.BytesIO(); c=Canvas(b);c.drawString(35,700,"Integrante NIT 900317964-1");c.showPage();c.save()
        pdf=b.getvalue()
        portfolio="CO1.BDOS.8263083"
        url="https://community.secop.gov.co/Public/Archive/RetrieveFile/Index?DocumentId=625136592"
        def src(addr):
            ds=urlsplit(addr).path.rsplit("/",1)[-1].removesuffix(".json")
            if ds=="dmgg-8hin":return [{"proceso":portfolio,"nombre_archivo":"CONTRATO 280.pdf",
                                        "id_documento":"625136592","url_descarga_documento":{"url":url}}]
            return []
        downloads=[]
        def download(uri):
            downloads.append(uri)
            return pdf
        store=Store("sqlite:///:memory:")
        try:
            store.create_schema()
            response=inspect_portfolio(portfolio,fetch=src,download=download,store=store)
            self.assertEqual(downloads,[url])
            self.assertEqual(response["indicators_detected"],1)
            self.assertEqual(response["documents_inspected"][0]["status"],"parsed")
            self.assertEqual(response["contract_proven_from_document"],0)
            self.assertEqual(response["file_bytes_persisted"],0)
            hints=store.find("900317964-1")
            self.assertEqual(hints["count_contracts"],0)
            self.assertEqual(hints["count_indicators"],1)
        finally:
            store.close()
