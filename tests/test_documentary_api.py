"""La API no transforma coincidencias del piloto en contratos acreditados."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen,Request
from urllib.error import HTTPError

from index28.api import build_handler
from index28.persistence import DocumentStore
from index28.evidence import parse_pdf
import test_document_pipeline as fixtures


class DocumentaryAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.url="sqlite:///"+str(Path(self.temp.name)/"pilot.sqlite3")
        store=DocumentStore(self.url)
        try:
            store.create_document_schema()
            key=store.enqueue("SECOP I",fixtures.REF,fixtures.document(),0)
            job=store.claim(key)
            result=parse_pdf(fixtures.pdf(["Informacion publicada NIT 900317964-1"]),
                source="ps88-5e3v",process_ref=fixtures.REF,process_url=fixtures.PROCESS,
                document_url="https://www.contratos.gov.co/archivos/PROCESO_"+fixtures.REF+"_123.pdf")
            store.finish(key,job["lease_token"],result)
        finally:store.close()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),build_handler(self.url))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_address[1]}"
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.temp.cleanup()
    def read(self,path):
        with urlopen(self.base+path,timeout=5) as r:return json.load(r)
    def test_page_evidence_and_partial_scope_are_exposed(self):
        response=self.read('/api/documentary/search?nit=900317964-1')
        self.assertEqual(response['count_observations'],1)
        self.assertEqual(response['observations'][0]['page'],1)
        self.assertEqual(response['observations'][0]['review_status'],'pending_review')
        self.assertFalse(response['national_coverage'])
        self.assertEqual(response['verified_contracts_from_observations'],0)
        self.assertEqual(response['coverage']['documents_stored'],0)
    def test_empty_pilot_result_never_certifies_absence(self):
        response=self.read('/api/documentary/search?nit=901601837-5')
        self.assertEqual(response['count_observations'],0)
        self.assertFalse(response['coverage']['absence_of_contracts_certified'])
    def test_no_write_or_arbitrary_url_route(self):
        for path in ['/api/documentary/search?nit=900317964-1&url=https://evil.test',
                     '/api/documentary/search?nit=900317964-1&nit=800143586-1',
                     '/api/documentary/search?nit=900317964-1&limit=201']:
            with self.assertRaises(HTTPError) as error:urlopen(self.base+path,timeout=5)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/documentary/search',data=b'{}',method='POST'),timeout=5)
        self.assertEqual(error.exception.code,405)
    def test_unavailable_database_is_503_not_empty_search(self):
        broken=ThreadingHTTPServer(('127.0.0.1',0),build_handler('sqlite:///'+str(Path(self.temp.name)/'missing.db')))
        thread=threading.Thread(target=broken.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(f'http://127.0.0.1:{broken.server_address[1]}/api/documentary/search?nit=900317964',timeout=5)
            self.assertEqual(error.exception.code,503)
            self.assertNotIn(b'missing.db',error.exception.read())
        finally:broken.shutdown();broken.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
