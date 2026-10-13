from __future__ import annotations
import unittest
from urllib.parse import parse_qs, urlsplit
from index28.secop_i_inventory import inventory, process_url, field_url, normal_proponent_nit, official_https_url, document_type


class TestSecopIInventory(unittest.TestCase):
    def test_exact_filter_rejects_injection(self):
        for raw in ("26-12-14816016' OR 1=1", "https://evil.com", "", "123", "26-12-14816016; DROP TABLE x"):
            with self.assertRaises(ValueError):
                field_url("ps88-5e3v", "numero_de_constancia", raw, 20, 0)
        url = field_url("ps88-5e3v", "numero_de_constancia", "26-12-14816016", 20, 0)
        self.assertEqual(parse_qs(urlsplit(url).query)["$where"], ["numero_de_constancia='26-12-14816016'"])

    def test_safe_download_links(self):
        self.assertIsNone(official_https_url("http://20.96.127.85/descarga/140064067"))
        self.assertIsNone(official_https_url({"url": "https://127.0.0.1/private"}))
        self.assertIsNone(official_https_url("https://www.contratos.gov.co.evil.com/hi"))
        self.assertEqual(official_https_url({"url": "https://www.contratos.gov.co/consultas/detalleProceso.do"}),
                         "https://www.contratos.gov.co/consultas/detalleProceso.do")

    def test_non_attribution(self):
        self.assertIsNone(normal_proponent_nit("No Definido"))
        self.assertEqual(normal_proponent_nit("800.143.586-1"), "800143586")
        self.assertIsNone(normal_proponent_nit("CONSORCIO MATEPANTANO"))

    def test_classification(self):
        self.assertEqual(document_type({"descripcion": "Poliza de cumplimiento"}), "garantias")
        self.assertEqual(document_type({"descripcion": "Informe Final Evaluacion"}), "evaluacion")
        self.assertEqual(document_type({"descripcion": "CDP"}), "otro")
        self.assertEqual(document_type({"descripcion": "Acta de inicio"}), "ejecucion_posible")

    def test_pilot_three_sources_without_document_download(self):
        calls = []
        def fetch(url):
            parsed = urlsplit(url)
            qs = parse_qs(parsed.query)
            calls.append((parsed.path, qs))
            if "ps88-5e3v" in url:
                return [{"identificador":"140064067", "nombrearchivo":"DP_PROCESO_26-12-14816016_140064067.pdf", "descripcion":"POLIZA CUMPLIMIENTO", "ruta_descarga":"http://20.96.127.85/descarga/140064067", "fecha_creacion":"2026-10-08T00:00:00.000"}]
            if "8kpz-m6cc" in url:
                return [{"identificador":"140064067", "nombrearchivo":"duplicado.pdf", "descripcion":"PÓLIZA", "ruta_descarga":{"url":"http://20.96.127.85/descarga/140064067"}}]
            if "tauh-5jvn" in url:
                return [{"id_proceso":"26-12-14816016", "proponente":"CONSORCIO EJEMPLO", "num_doc_proponente":"No Definido", "adjudicado":"Si", "numero_contrato":"No Definido"}]
            raise AssertionError("unexpected path")
        result = inventory("26-12-14816016", fetch)
        self.assertEqual(len(result["documents"]), 1)
        self.assertEqual(len(result["proponents"]), 1)
        self.assertIsNone(result["proponents"][0]["nit"])
        self.assertTrue(result["proponents"][0]["awarded_in_dataset"])
        self.assertEqual(result["contracts_proven_by_metadata_only"], 0)
        self.assertEqual(result["document_read_count"], 0)
        self.assertEqual(result["document_bytes_persisted"], 0)
        self.assertIsNone(result["documents"][0]["verified_https_url"])
        self.assertEqual(result["documents"][0]["document_type"], "garantias")
        self.assertEqual(len(calls), 3)
        self.assertTrue(result["requested_sources_returned_without_error"])
        self.assertEqual(result["national_coverage"], "no_acreditada")

    def test_failure_not_silent(self):
        def fetch(url):
            if "8kpz-m6cc" in url: raise ConnectionError("fuente no disponible")
            return []
        result=inventory("17-1-169268",fetch)
        self.assertFalse(result["requested_sources_returned_without_error"])
        self.assertEqual([e["state"] for e in result["coverage"]], ["ok","failed","ok"])
        self.assertIn("no disponible", result["coverage"][1]["error"])

    def test_older_process_codes(self):
        self.assertEqual(process_url("05-1-893"), "https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia=05-1-893")

    def test_process_link_is_official(self):
        self.assertEqual(process_url("17-1-169268"), "https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia=17-1-169268")


if __name__ == '__main__':
    unittest.main()
