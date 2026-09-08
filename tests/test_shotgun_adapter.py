import copy
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from suiteviagem.adapters.shotgun import search, ticket, normalize
from suiteviagem.history import History
EVENT={'name':'Teste','startDate':'2026-09-12T23:00:00-03:00','endDate':'2026-09-13T08:00:00-03:00','offers':[{'price':'35','priceCurrency':'BRL','availability':'https://schema.org/SoldOut'},{'price':'45','priceCurrency':'BRL','availability':'https://schema.org/LimitedAvailability'}]}
class Engine:
    time=SimpleNamespace(sleep=lambda seconds:None)
    criar_slug=staticmethod(lambda city:'sao-paulo')
    pagina_da_cidade_valida=staticmethod(lambda page:True)
    obter_inicio_local=staticmethod(lambda event:datetime.fromisoformat(event['startDate']))
    obter_local=staticmethod(lambda event:'São Paulo')
    obter_organizador=staticmethod(lambda event:'Organizador')
    resumir_lineup=staticmethod(lambda event:'Artista')
    localizar_music_event=staticmethod(lambda page:page)
    def coletar_links(self,url,summary):
        summary.update(paginas_lidas=2,fim_agenda='página sem novos links',falhas_agenda=[])
        return ['https://shotgun.live/en/events/one','https://shotgun.live/en/events/two']
    def baixar_pagina(self,url):return copy.deepcopy(EVENT)
class AdapterTests(unittest.TestCase):
    def test_price_and_window(self):
        instant=datetime(2026,9,8,tzinfo=timezone.utc)
        price,_,_=ticket(EVENT,instant)
        self.assertEqual(price['amount_minor'],4500)
        self.assertIsNone(price['total_minor'])
        event=copy.deepcopy(EVENT)
        event['offers'][1]['validFrom']='2026-10-01T00:00:00Z'
        self.assertIsNone(ticket(event,instant)[0])
    def test_currency_zero_unknown(self):
        event=copy.deepcopy(EVENT)
        event['offers'][1]['price']='0'
        self.assertEqual(ticket(event,datetime.now(timezone.utc))[0]['amount_minor'],0)
        event['offers'][1]['priceCurrency']='EUR'
        self.assertIsNone(ticket(event,datetime.now(timezone.utc))[0])
        event['offers'][1]['availability']='Unknown'
        self.assertIsNone(ticket(event,datetime.now(timezone.utc))[0])
    def test_limit_and_roundtrip(self):
        with History(':memory:') as h:
            r=search(h,'São Paulo','2026-09-12','2026-09-13',1,engine=Engine(),log=lambda m:None)
            self.assertEqual(r['status'],'succeeded')
            self.assertEqual(r['coverage']['status'],'partial')
            self.assertEqual(len(r['results']),1)
            self.assertEqual(h.get(r['query_id']),r)
            self.assertEqual(r['results'][0]['period']['end'],'2026-09-13T08:00:00-03:00')
    def test_failure_and_cancel_preserve(self):
        for exception,status in [(RuntimeError,'failed'),(KeyboardInterrupt,'cancelled')]:
            class Broken(Engine):
                def baixar_pagina(self,url):
                    if url.endswith('/two'):raise exception()
                    return super().baixar_pagina(url)
            with History(':memory:') as h:
                r=search(h,'São Paulo','2026-09-12','2026-09-13',5,engine=Broken(),log=lambda m:None)
                self.assertEqual(r['status'],status)
                self.assertEqual(len(r['results']),1)
    def test_empty_and_bad_city(self):
        with History(':memory:') as h:
            r=search(h,'São Paulo','2026-10-12','2026-10-13',5,engine=Engine(),log=lambda m:None)
            self.assertEqual(r['results'],[])
            self.assertEqual(r['status'],'succeeded')
            engine=Engine()
            engine.pagina_da_cidade_valida=lambda page:False
            r=search(h,'São Paulo','2026-09-12','2026-09-13',engine=engine,log=lambda m:None)
            self.assertEqual(r['status'],'failed')
    def test_naive_date(self):
        event=copy.deepcopy(EVENT)
        event['startDate']='2026-09-12T23:00:00'
        with self.assertRaises(ValueError):normalize(event,'unused',Engine())
