import copy
from types import SimpleNamespace
import unittest
from suiteviagem.adapters.booking import price_from_text,search
from suiteviagem.history import History
ROW={'Hotel Name':'Hotel teste','Check-in':'2026-09-12','Check-out':'2026-09-13','Adults':2,'Children':0,'Rooms':1,'Nights':1,'Currency':'BRL','Price Text':'R$ 270','Taxes Text':'+ R$ 19 em impostos e taxas','Stars':'Não informado','Collected At':'2026-09-08T11:00:00-03:00'}
class BookingTests(unittest.TestCase):
    def test_added_included_unknown(self):
        row=copy.deepcopy(ROW)
        self.assertEqual(price_from_text(row)['total_minor'],28900)
        row['Taxes Text']='Impostos e taxas incluídos'
        self.assertEqual(price_from_text(row)['total_minor'],27000)
        row['Taxes Text']='Não informado'
        self.assertIsNone(price_from_text(row)['total_minor'])
    def test_cents_and_currency(self):
        row=copy.deepcopy(ROW);row['Price Text']='R$ 1.234,56'
        self.assertEqual(price_from_text(row)['amount_minor'],123456)
        row['Currency']='EUR'
        self.assertIsNone(price_from_text(row))
    def test_roundtrip_missing_price(self):
        rows=[copy.deepcopy(ROW),copy.deepcopy(ROW)]
        rows[1]['Price Text']='Não informado'
        e=SimpleNamespace(run_scraping=lambda *a,**k:{'records':rows,'excel':'test.xlsx','search_url':'test'})
        with History(':memory:') as h:
            r=search(h,'Petrópolis','2026-09-12','2026-09-13',engine=e,log=lambda m:None)
            self.assertEqual(r['status'],'succeeded')
            self.assertEqual(len(r['results']),2)
            self.assertIsNone(r['results'][1]['price'])
            self.assertIsNone(r['results'][0]['details']['stars'])
            self.assertEqual(h.get(r['query_id']),r)
    def test_mismatch_failure_cancel(self):
        row=copy.deepcopy(ROW);row['Adults']=3
        e=SimpleNamespace(run_scraping=lambda *a,**k:{'records':[row]})
        with History(':memory:') as h:
            r=search(h,'Petrópolis','2026-09-12','2026-09-13',engine=e,log=lambda m:None)
            self.assertEqual(r['status'],'failed')
        for exception,status in [(RuntimeError,'failed'),(KeyboardInterrupt,'cancelled')]:
            def fail(*a,**k):raise exception()
            with History(':memory:') as h:
                r=search(h,'Petrópolis','2026-09-12','2026-09-13',engine=SimpleNamespace(run_scraping=fail),log=lambda m:None)
                self.assertEqual(r['status'],status)
