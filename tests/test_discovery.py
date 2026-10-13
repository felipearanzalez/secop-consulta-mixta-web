"""El indexador encuentra constancias desconocidas sin recibir NIT o PDF manual."""
import tempfile
from pathlib import Path
import unittest
from urllib.parse import parse_qs,urlsplit

from index28.persistence import DocumentStore
from index28.discovery import seed_plural,discovery_url
from index28 import checkpoints


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=DocumentStore("sqlite:///"+str(Path(self.tmp.name)/"index.db"))
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def inventory(self,ref,fetch=None):
        return {"platform":"SECOP I","reference":ref,"document_metadata":[
          {"id":"123","name":"Evaluacion.pdf","source":"ps88-5e3v"}],
          "coverage":[{"status":"ok"}],"complete_in_requested_sources":True}
    def test_seed_without_nit_and_repeat_keeps_queue(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if "uid+%3E" in url:return []
            return [{"uid":"26-11-14749233-1","numero_de_constancia":"26-11-14749233",
                     "nom_razon_social_contratista":"CONSORCIO PRUEBA"}]
        result=seed_plural(self.store,fetch=fetch,inventory_fn=self.inventory,limit=2)
        self.assertEqual(result["persisted_processes"],1)
        self.assertEqual(result["processes"][0]["documents_queued"],1)
        self.assertNotIn("900317964",str(calls))
        repeated=seed_plural(self.store,fetch=fetch,inventory_fn=self.inventory,limit=2)
        self.assertEqual(repeated["persisted_processes"],0)
        self.assertEqual(self.store.rows("SELECT count(*) AS n FROM index_doc_jobs")[0]["n"],1)
    def test_failed_inventory_does_not_skip_that_process(self):
        rows=[{"uid":"26-11-14749233-1","numero_de_constancia":"26-11-14749233"},
              {"uid":"26-11-14749234-1","numero_de_constancia":"26-11-14749234"}]
        def partial(ref,fetch=None):
            src=self.inventory(ref)
            if ref.endswith("234"):src["complete_in_requested_sources"]=False
            return src
        result=seed_plural(self.store,fetch=lambda url:rows,inventory_fn=partial,limit=2)
        self.assertEqual(result["status"],"partial")
        checkpoint=checkpoints.read(self.store,"f789-7hwg","plural_initial")
        self.assertEqual(checkpoint["cursor"],"26-11-14749233-1")
        self.assertEqual(self.store.rows("SELECT count(*) AS n FROM index_doc_jobs")[0]["n"],2)
    def test_error_does_not_replace_previous_cursor(self):
        self.store.create_document_schema();checkpoints.ensure_schema(self.store)
        checkpoints.record(self.store,"f789-7hwg","plural_initial",status="ok",count=1,cursor="26-11-14749233-1")
        def fail(url):raise ConnectionError("429")
        result=seed_plural(self.store,fetch=fail)
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["cursor"],"26-11-14749233-1")
    def test_input_validation_and_lexical_order(self):
        for value in ["x' OR 1=1", "bad", "26-11-123;DROP TABLE"]:
            with self.assertRaises(ValueError):discovery_url("f789-7hwg",value)
        with self.assertRaises(ValueError):discovery_url("dmgg-8hin")
        result=seed_plural(self.store,fetch=lambda url:[
             {"uid":"26-11-14749234-1"},{"uid":"26-11-14749233-1"}],limit=2)
        self.assertEqual(result["status"],"failed")


if __name__=="__main__":unittest.main()
