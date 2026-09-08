import copy
from types import SimpleNamespace
import unittest
from suiteviagem.adapters.google_flights import search
from suiteviagem.history import History
REPORT={'datas':['2026-09-13','2026-09-14'],'sucessos':[{'data':'2026-09-13','preco':1234.56},{'data':'2026-09-14','preco':1200}],
        'falhas':[],'preco':1200,'data':'2026-09-14','url':'https://www.google.com/travel/flights','passo':1,'ida_volta':False,'duracao':7}
def engine(report=None):
    return SimpleNamespace(raspar_melhor_preco=lambda *a:copy.deepcopy(report or REPORT),
        montar_url=lambda *a:'https://www.google.com/travel/flights?date='+a[2],
        criar_rss_local=lambda *a:'feed.xml')
class FlightsTests(unittest.TestCase):
    def test_roundtrip_sort_and_money(self):
        with History(':memory:') as h:
            r=search(h,'RIO','SAO',engine=engine(),log=lambda m:None)
            self.assertEqual(r['status'],'succeeded')
            self.assertEqual(r['coverage']['status'],'complete_for_scope')
            self.assertEqual(r['results'][0]['price']['amount_minor'],120000)
            self.assertEqual(r['results'][1]['price']['amount_minor'],123456)
            self.assertIsNone(r['results'][0]['price']['total_minor'])
            self.assertEqual(h.get(r['query_id']),r)
    def test_round_trip_dates(self):
        with History(':memory:') as h:
            r=search(h,'RIO','SAO',roundtrip=True,duration=3,engine=engine(),log=lambda m:None)
            self.assertEqual(r['results'][0]['period']['end'],'2026-09-17')
    def test_partial_failure(self):
        report=copy.deepcopy(REPORT)
        report['sucessos']=report['sucessos'][:1]
        report['falhas']=[{'data':'2026-09-14','erro':'timeout','tentativas':['timeout','timeout']}]
        with History(':memory:') as h:
            r=search(h,'RIO','SAO',engine=engine(report),log=lambda m:None)
            self.assertEqual(r['status'],'failed')
            self.assertEqual(len(r['results']),1)
            self.assertEqual(r['errors'][0]['attempts'],['timeout','timeout'])
    def test_no_prices_preserves_feed(self):
        report=copy.deepcopy(REPORT);report['sucessos']=[];report['preco']=None
        e=engine(report)
        def forbidden(*args):raise AssertionError('Não deve escrever feed')
        e.criar_rss_local=forbidden
        with History(':memory:') as h:
            r=search(h,'RIO','SAO',engine=e,rss=True,log=lambda m:None)
            self.assertEqual(r['status'],'failed');self.assertEqual(r['results'],[])
    def test_feed_success_failure(self):
        for fail in (False,True):
            calls=[];e=engine()
            def feed(*args):
                calls.append(args)
                if fail:raise OSError('Sem espaço')
                return 'feed.xml'
            e.criar_rss_local=feed
            with History(':memory:') as h:
                r=search(h,'RIO','SAO',engine=e,rss=True,log=lambda m:None)
                self.assertEqual(r['status'],'succeeded')
                self.assertEqual(len(r['results']),2)
                self.assertEqual(len(calls),1)
                self.assertEqual(calls[0][3]['preco'],1200)
                self.assertTrue(any('Falha' in w for w in r['warnings']) if fail else any('atualizado' in w for w in r['warnings']))
    def test_cancel_and_invalid(self):
        e=engine()
        def cancel(*args):raise KeyboardInterrupt
        e.raspar_melhor_preco=cancel
        with History(':memory:') as h:
            r=search(h,'RIO','SAO',engine=e,log=lambda m:None)
            self.assertEqual(r['status'],'cancelled')
            with self.assertRaises(ValueError):search(h,'RIO','RIO',engine=e)
    def test_duplicate_date(self):
        report=copy.deepcopy(REPORT);report['sucessos'].append(report['sucessos'][0])
        with History(':memory:') as h:
            r=search(h,'RIO','SAO',engine=engine(report),log=lambda m:None)
            self.assertEqual(r['status'],'failed')
