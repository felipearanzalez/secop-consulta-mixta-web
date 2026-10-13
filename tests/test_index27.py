"""Regression tests: evidence-only persistence, attribution, HTTP read-only API."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from index27.store import Store, normalize_nit, validate_contract, validated_url
from index27.api import Handler

ROOT=Path(__file__).resolve().parents[1]
CASE=json.loads((ROOT/'index27/verified_cases.json').read_text())[0]

class Index27Test(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'index.sqlite3'
        self.url='sqlite:///'+str(self.path)
        self.store=Store(self.url)
        self.store.create_schema()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_seed_and_search_three_participants(self):
        self.assertEqual(self.store.import_cases(ROOT/'index27/verified_cases.json'),1)
        for nit,share in [('800143586-1','10'),('901505828-8','80'),('901601837-5','10')]:
            result=self.store.find(nit)
            self.assertEqual(result['count_contracts'],1)
            row=result['contracts'][0]
            self.assertEqual(row['share_percent'],share)
            self.assertEqual(row['contract_ref'],'Contrato de Obra Publica 002 de 2026')
            self.assertEqual(row['execution_class'],'firma_acreditada_ejecucion_no_verificada')
            self.assertEqual({s['kind'] for s in row['sources']},{'contrato_firmado','composicion_plural','secop_expediente'})
            self.assertTrue(all(s['url'].startswith('https://') for s in row['sources']))
        self.assertEqual(self.store.find('900000001')['contracts'],[])
        self.assertEqual(self.store.import_cases(ROOT/'index27/verified_cases.json'),1)
        self.assertEqual(self.store.find('800143586')['count_contracts'],1)

    def test_no_pdf_binaries_are_stored(self):
        self.store.import_cases(ROOT/'index27/verified_cases.json')
        tables=self.store.rows("SELECT name FROM sqlite_master WHERE type='table'")
        names={v['name'] for v in tables}
        self.assertFalse(any('document_bytes' in name or 'pdf_blob' in name for name in names))
        self.assertTrue(self.path.stat().st_size<100000)

    def test_unverified_mentions_not_contracts(self):
        self.store.upsert_indicator({'source':'asosupro','nit':'800143586','process_ref':'LP-111-2026',
         'process_url':CASE['process_url'],'document_url':CASE['evidence'][1]['url'],
         'page':4,'excerpt':'MEYAN was present in an unrelated document'})
        r=self.store.find('800143586-1')
        self.assertEqual(r['count_contracts'],0)
        self.assertEqual(r['count_indicators'],1)
        self.assertEqual(r['indicators'][0]['verification_status'],'indicio_no_verificado')

    def test_evidence_validation(self):
        for variant in ('800.143.586-1','8001435861','800143586-1'):
            self.assertEqual(normalize_nit(variant),'800143586')
        for invalid in ('123','90000000000000','1-2','https://abc.test','../bad'):
            with self.assertRaises(ValueError):normalize_nit(invalid)
        for invalid in ('http://contratacion.asosupro.gov.co/file.pdf',
                        'https://contratacion.asosupro.gov.co.evil.test/file.pdf',
                        'https://contratacion.asosupro.gov.co@evil.test/index',
                        'https://127.0.0.1/index'):
            with self.assertRaises(ValueError):validated_url(invalid)
        incomplete=copy.deepcopy(CASE);incomplete['evidence']=[CASE['evidence'][0]]
        with self.assertRaisesRegex(ValueError,'prueba documental'):validate_contract(incomplete)
        incomplete=copy.deepcopy(CASE);incomplete['members'][1]['share_percent']=79
        with self.assertRaisesRegex(ValueError,'100'):validate_contract(incomplete)
        incomplete=copy.deepcopy(CASE);incomplete['members'][2]['nit']='800143586'
        with self.assertRaisesRegex(ValueError,'repetido'):validate_contract(incomplete)

    def test_api_same_record_and_read_only(self):
        self.store.import_cases(ROOT/'index27/verified_cases.json')
        previous=os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL']=self.url
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
        base=f'http://127.0.0.1:{server.server_address[1]}'
        try:
            with urlopen(base+'/health',timeout=5) as r:
                response=json.load(r)
                self.assertEqual(response['contract_records'],1)
                self.assertEqual(response['documents_stored'],0)
            with urlopen(base+'/api/index/search?nit=800143586-1',timeout=5) as r:
                response=json.load(r)
                self.assertEqual(response['count_contracts'],1)
                self.assertEqual(r.headers.get('Access-Control-Allow-Origin'),'https://secop-consulta-mixta-web.onrender.com')
            for bad in ['/api/index/search?nit=800143586-1&other=1','/api/index/search?nit=bad','/api/index/search']:
                with self.assertRaises(HTTPError) as ctx:urlopen(base+bad,timeout=5)
                self.assertEqual(ctx.exception.code,400)
            req=Request(base+'/api/index/search?nit=800143586',method='POST',data=b'{}')
            with self.assertRaises(HTTPError) as ctx:urlopen(req,timeout=5)
            self.assertEqual(ctx.exception.code,405)
        finally:
            server.shutdown();server.server_close();th.join(timeout=2)
            if previous is None:os.environ.pop('DATABASE_URL',None)
            else:os.environ['DATABASE_URL']=previous

if __name__=='__main__':unittest.main()
