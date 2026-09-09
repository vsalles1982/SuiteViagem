import copy
import unittest
from types import SimpleNamespace as NS
from test_hotels_fast import functions
from test_booking_adapter import ROW
from suiteviagem.adapters.booking import search
from suiteviagem.history import History

class ProgressTests(unittest.TestCase):
    def test_price_tax_changes_and_removal(self):
        ns={};exec(functions('stable_batch'),ns);seen={}
        r={'Hotel Name':'Hotel','Hotel URL':'https://www.booking.com/hotel/br/test.html?x=1','Price':10,'Price Text':'R$ 10','Taxes Text':'incluídos'}
        f=ns['stable_batch'];self.assertEqual(f([r],seen,0),[]);self.assertEqual(f([r],seen,3),[r])
        r={**r,'Taxes Text':'+ R$ 5'};self.assertEqual(f([r],seen,4),[]);self.assertEqual(f([r],seen,7),[r])
        self.assertEqual(f([],seen,8),[]);self.assertEqual(f([r],seen,9),[])
    def test_first_batch_survives_cancel_not_later_batch(self):
        initial=copy.deepcopy(ROW);later={**initial,'Price Text':'R$ 900'}
        def run(*args,**kwargs):
            kwargs['on_progress']([initial]);kwargs['on_progress']([later]);raise KeyboardInterrupt()
        with History(':memory:') as h:
            events=[];r=search(h,'Petrópolis','2026-09-12','2026-09-13',engine=NS(run_scraping=run),on_progress=events.append,log=lambda m:None,fast=True)
            self.assertEqual(len(events),2);self.assertEqual(r['status'],'cancelled')
            self.assertEqual(r['results'][0]['price']['amount_minor'],27000)
            self.assertEqual(h.get(r['query_id']),r)
    def test_final_replaces_preview(self):
        row=copy.deepcopy(ROW)
        def run(*args,**kwargs):
            kwargs['on_progress']([row]);return {'records':[{**row,'Price Text':'R$ 300'}]}
        with History(':memory:') as h:
            r=search(h,'Petrópolis','2026-09-12','2026-09-13',engine=NS(run_scraping=run),on_progress=lambda e:None,log=lambda m:None,fast=True)
            self.assertEqual(r['status'],'succeeded');self.assertEqual(r['results'][0]['price']['amount_minor'],30000)
    def test_preview_not_saved_as_success_on_failure(self):
        def run(*args,**kwargs):
            kwargs['on_progress']([copy.deepcopy(ROW)]);raise RuntimeError('Consulta mudou')
        with History(':memory:') as h:
            r=search(h,'Petrópolis','2026-09-12','2026-09-13',engine=NS(run_scraping=run),on_progress=lambda e:None,log=lambda m:None,fast=True)
            self.assertEqual(r['status'],'failed');self.assertEqual(r['results'],[])
    def test_server_keeps_first_preview_and_recovers_cancel(self):
        import json,io,tempfile,time
        from collections import deque
        from pathlib import Path
        from suiteviagem.web.server import Jobs
        from suiteviagem.core.models import new_query
        from suiteviagem.adapters.booking import normalize
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'h.sqlite3'
            with History(db) as h:
                q=new_query('hotels',{});qid=h.create(q);h.start(qid)
            first={'query_id':qid,'module':'hotels','results':[normalize(copy.deepcopy(ROW),qid,'2026-09-12','2026-09-13')]}
            second={**first,'results':[]}
            j=Jobs(db);j.job={'query_id':qid,'status':'cancelling','logs':deque(),'first_preview':None,'preview_version':0}
            j.process=NS(stdout=io.StringIO('SUITE_PREVIEW:'+json.dumps(first)+'\nSUITE_PREVIEW:'+json.dumps(second)+'\n'),wait=lambda:130)
            j._read()
            self.assertEqual(j.job['preview']['results'],[])
            self.assertEqual(j.job['first_preview'],first)
            with History(db) as h:
                q=h.get(qid);self.assertEqual(q['status'],'cancelled');self.assertEqual(q['results'],first['results'])
    def test_first_batch_before_scroll(self):
        clock=[0.0];events=[]
        row={'Hotel Name':'Test','Hotel URL':'https://www.booking.com/hotel/br/test.html','Price':10,'Price Text':'R$ 10','Taxes Text':'Impostos e taxas incluídos'}
        ns={'time':NS(monotonic=lambda:clock[0],sleep=lambda v:clock.__setitem__(0,clock[0]+v)),
            'read_cards_batch':lambda d:([row],'https://www.booking.com/')}
        exec(functions('stable_batch','extract_fast_batch'),ns)
        d=NS(execute_script=lambda script:events.append('scroll'))
        result=ns['extract_fast_batch'](d,on_progress=lambda rows:events.append('preview'),confirm=lambda url:True)
        self.assertEqual(events[0],'preview');self.assertEqual(result,[row]);self.assertGreaterEqual(clock[0],12)
