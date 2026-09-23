import copy,io,json,tempfile,unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from collections import deque
from suiteviagem.adapters.discovercars import search,normalize
from suiteviagem.history import History
from suiteviagem.core.models import new_query
from suiteviagem.web.server import Jobs,command
from test_cars_adapter import engine,DATA

class CarProgressTests(unittest.TestCase):
    def test_first_preserved_on_cancel_and_final_replaces(self):
        for outcome in ('cancel','success','failure'):
            e,row=engine();events=[];original=e.coletar_ofertas
            def run(*args,on_progress):
                on_progress({'consulta':DATA,'resultados':[row]})
                row['TotalBRL']=Decimal('200.00')
                on_progress({'consulta':DATA,'resultados':[row]})
                if outcome=='cancel':raise KeyboardInterrupt()
                if outcome=='failure':raise ValueError('Consulta mudou')
                return original(*args)
            e.coletar_ofertas=run
            with History(':memory:') as h:
                r=search(h,'Ibiza Airport','2026-09-12','2026-09-13',engine=e,log=lambda m:None,on_progress=events.append)
                self.assertEqual(len(events),2)
                self.assertEqual(events[0]['results'][0]['price']['amount_minor'],18967)
                self.assertEqual(r,h.get(r['query_id']))
                if outcome=='failure':self.assertEqual(r['results'],[]);self.assertEqual(r['status'],'failed')
                else:self.assertEqual(r['results'][0]['price']['amount_minor'],18967 if outcome=='cancel' else 20000)
    def test_bad_dates_never_emit(self):
        e,row=engine();events=[]
        def run(*args,on_progress):on_progress({'consulta':{**DATA,'PickupDateTime':'2026-09-11T11:00:00'},'resultados':[row]})
        e.coletar_ofertas=run
        with History(':memory:') as h:
            r=search(h,'Airport','2026-09-12','2026-09-13',engine=e,log=lambda m:None,on_progress=events.append)
            self.assertEqual(events,[]);self.assertEqual(r['status'],'failed')
    def test_server_accepts_cars_and_recovers_first_only(self):
        e,row=engine()
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'history.sqlite3'
            with History(db) as h:
                q=new_query('cars',{});qid=h.create(q);h.start(qid)
            first={'query_id':qid,'module':'cars','effective':DATA,'results':[normalize(row,qid,e,DATA)]}
            wrong={**first,'module':'hotels','results':[]}
            j=Jobs(db);j.job={'module':'cars','query_id':qid,'status':'cancelling','logs':deque(),'first_preview':None,'preview_version':0}
            j.process=SimpleNamespace(stdout=io.StringIO('\n'.join('SUITE_PREVIEW:'+json.dumps(x) for x in (first,wrong))),wait=lambda:130)
            j._read()
            self.assertEqual(j.job['preview_version'],1)
            with History(db) as h:
                saved=h.get(qid);self.assertEqual(saved['status'],'cancelled');self.assertEqual(saved['results'],first['results']);self.assertEqual(saved['effective'],DATA)
    def test_web_enables_progress(self):
        args=command(dict(module='cars',destination='Airport',start='2026-09-12',end='2026-09-13',limit=5),Path('/tmp/test.sqlite3'))
        self.assertIn('--progressivo',args)
    def test_legacy_engine_accepts_web_request_without_callback_argument(self):
        from test_cars_adapter import engine
        e,_=engine();received=[]
        with History(':memory:') as h:
            q=search(h,'Airport','2026-09-12','2026-09-13',engine=e,log=lambda m:None,on_progress=received.append)
            self.assertEqual(q['status'],'succeeded')
            self.assertTrue(q['results'])
            self.assertEqual(received,[])
            self.assertEqual(q,h.get(q['query_id']))
