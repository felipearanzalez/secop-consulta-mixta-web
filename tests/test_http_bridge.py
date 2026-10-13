import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import croma_backend as bridge

TOKEN='x'*32
ORIGIN='https://secop-consulta-mixta-web.onrender.com'


class TestHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),bridge.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def req(self,method,path,content=None,headers=None):
        cn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        h=headers or {};cn.request(method,path,json.dumps(content) if content is not None else None,headers=h)
        response=cn.getresponse(); raw=response.read(); code=response.status
        hdr={k.lower():v for k,v in response.getheaders()};cn.close()
        return code,hdr,json.loads(raw or '{}')
    def test_health_unconfigured(self):
        with patch.object(bridge,'CROMA_KEY',''),patch.object(bridge,'APP_SECRET',''):
            st,headers,data=self.req('GET','/health',headers={'Origin':ORIGIN})
        self.assertEqual(st,200);self.assertFalse(data['configured']);self.assertEqual(headers.get('access-control-allow-origin'),ORIGIN)
    def test_origin_cors_reject(self):
        st,headers,data=self.req('OPTIONS','/api/croma/search',headers={'Origin':'https://evil.example'})
        self.assertEqual(st,204);self.assertNotIn('access-control-allow-origin',headers)
    def test_unauthorized_and_no_auth_leaks(self):
        payload={'document':'800143586-1'}
        with patch.object(bridge,'CROMA_KEY','test-secret'),patch.object(bridge,'APP_SECRET',TOKEN):
            st,headers,data=self.req('POST','/api/croma/search',payload,{'Origin':ORIGIN,'Content-Type':'application/json','X-SECOP-Access':'wrong'})
        self.assertEqual(st,401);self.assertNotIn('test-secret',str(data));self.assertNotIn(TOKEN,str(data))
    def test_wrong_origin_denied_even_when_key_valid(self):
        with patch.object(bridge,'CROMA_KEY','test-secret'),patch.object(bridge,'APP_SECRET',TOKEN):
            st,_,_=self.req('POST','/api/croma/search',{'document':'800143586-1'},{'Origin':'https://evil.example','Content-Type':'application/json','X-SECOP-Access':TOKEN})
        self.assertEqual(st,403)
    def test_valid_route(self):
        def stub(p):return {'data':{'results':[{'id':'secop_i:26-11-14749233','platform':'secop_i','contract_id':'c1'}], 'total_pages':1,'total':1,'as_of':'2026-10-10'}}
        with patch.object(bridge,'CROMA_KEY','test-secret'),patch.object(bridge,'APP_SECRET',TOKEN),patch.object(bridge,'request_croma',stub):
            # search() default fn bound at definition; patch search with a safe direct stub.
            original=bridge.search
            with patch.object(bridge,'search',lambda body:original(body,api_call=stub)):
                st,headers,data=self.req('POST','/api/croma/search',{'document':'800143586-1'}, {'Origin':ORIGIN,'Content-Type':'application/json','X-SECOP-Access':TOKEN})
        self.assertEqual(st,200);self.assertEqual(len(data['direct']['records']),1);self.assertIsNone(data['representative_candidates']);self.assertEqual(headers.get('cache-control'),'no-store')
    def test_disallow_unexpected_parameters(self):
        with patch.object(bridge,'CROMA_KEY','test-secret'),patch.object(bridge,'APP_SECRET',TOKEN):
            st,_,_=self.req('POST','/api/croma/search',{'document':'800143586-1','url':'https://evil.example'},{'Origin':ORIGIN,'Content-Type':'application/json','X-SECOP-Access':TOKEN})
        self.assertEqual(st,400)

if __name__=='__main__':unittest.main()
