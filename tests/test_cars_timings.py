import ast,unittest
from pathlib import Path
from types import SimpleNamespace
from suiteviagem.adapters.discovercars import search
from suiteviagem.history import History
from test_cars_adapter import engine

class TimingTests(unittest.TestCase):
    def timer(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scraper_carro/discovercars.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TemposCarros']
        ns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'timer','exec'),ns)
        self.now=0
        return ns['TemposCarros'](clock=lambda:self.now)
    def test_elapsed_first_and_cleanup(self):
        t=self.timer();self.now=1;t.enter('driver_seconds');self.now=3;t.enter('collection_seconds');self.now=5;t.first_batch();self.now=6;t.first_batch();self.now=7;t.enter('cleanup_seconds');self.now=8;t.finish()
        self.assertEqual(t.values,{'validation_seconds':1,'driver_seconds':2,'first_batch_seconds':5,'collection_seconds':4,'cleanup_seconds':1,'total_seconds':8})
    def test_history_success_error_cancel(self):
        for exc,mismatch in ((None,False),(None,True),(ValueError,False),(KeyboardInterrupt,False)):
            e,_=engine();original=e.coletar_ofertas;t=self.timer()
            def collect(*a):
                try:
                    self.now=2;t.enter('collection_seconds')
                    if exc:
                        error=exc('interrompido');error.car_timings=t.values;raise error
                    report=original(*a);report['timings']=t.values;return report
                finally:
                    self.now=5;t.enter('cleanup_seconds');self.now=6.125;t.finish()
            e.coletar_ofertas=collect
            with History(':memory:') as h:
                q=search(h,'Airport','2026-09-13' if mismatch else '2026-09-12','2026-09-14' if mismatch else '2026-09-13',engine=e,log=lambda m:None)
                self.assertEqual(q['status'],'cancelled' if exc is KeyboardInterrupt else 'failed' if exc or mismatch else 'succeeded')
                # Fixture original uses 12–13; mismatch still must keep engine timings.
                metrics={m['name']:m['value'] for m in q['coverage']['metrics']}
                self.assertEqual(metrics['total_milliseconds'],6125)
                self.assertEqual(metrics['cleanup_milliseconds'],1125)
                self.assertEqual(q,h.get(q['query_id']))
