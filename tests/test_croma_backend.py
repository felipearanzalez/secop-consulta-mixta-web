import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import croma_backend as bridge

class TestCroma(unittest.TestCase):
    def test_invalid_id(self):
        for s in ('test', '9; DROP TABLE', '123', '888-22'):
            with self.subTest(s=s), self.assertRaises(bridge.ApiFault): bridge.as_document(s)
    def test_valid_id(self):
        self.assertEqual(bridge.as_document('800143586-1'),'800143586-1')
    def test_not_ready_without_secret(self):
        with patch.object(bridge,'CROMA_KEY','xx'),patch.object(bridge,'APP_SECRET',''):
            self.assertFalse(bridge.ready())
    def test_pagination_and_provenance(self):
        calls=[]
        def fake(arg):
            calls.append(arg)
            i=arg['page'];return {'data':{'results':[{'contract_id':f'C{i}','platform':'secop_i'}],
                              'total':3,'total_pages':3,'as_of':'2026-10-01'}}
        with patch.object(bridge,'MAX_PAGES',2):
            output=bridge.collect('800143586-1','provider_document',api_call=fake)
        self.assertEqual(output['count_returned'],2)
        self.assertTrue(output['truncated'])
        self.assertEqual(output['total_reported'],3)
        self.assertEqual(output['as_of'],'2026-10-01')
        self.assertEqual([a['page'] for a in calls],[1,2])
        self.assertEqual(calls[0]['provider_document'],'800143586-1')
    def test_representative_not_direct(self):
        def fake(arg):
            code = 'REP' if 'legal_rep_document' in arg else 'DIRECT'
            return {'data':{'results':[{'contract_id':code}],'total':1,'total_pages':1}}
        data=bridge.search({'document':'800143586-1','representative_document':'111222333'},api_call=fake)
        self.assertEqual(data['direct']['records'][0]['contract_id'],'DIRECT')
        self.assertEqual(data['representative_candidates']['records'][0]['contract_id'],'REP')
    def test_no_rep_query_without_id(self):
        calls=[]
        def fake(arg):
            calls.append(arg);return {'data':{'results':[],'total':0,'total_pages':1}}
        self.assertIsNone(bridge.search({'document':'800143586-1'},api_call=fake)['representative_candidates'])
        self.assertEqual(len(calls),1)
    def test_error_empty_and_shapes(self):
        with self.assertRaises(bridge.ApiFault):bridge.unpack_api({'data':{'results':'no'}})
    def test_limit_per_ip(self):
        with patch.object(bridge,'DAILY_LIMIT',1):
            with bridge._lock:bridge._requests.clear()
            bridge.rate_limit('127.0.0.2')
            with self.assertRaises(bridge.ApiFault):bridge.rate_limit('127.0.0.2')
    def test_known_fixed_upstream_only(self):
        self.assertEqual(bridge.CROMA_ENDPOINT,'https://api.croma.run/co/secop/contracts-search/v1')

if __name__=='__main__': unittest.main()
