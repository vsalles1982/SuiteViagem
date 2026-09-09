import unittest
import sys
from types import SimpleNamespace as NS, ModuleType
from unittest.mock import patch
from urllib.parse import urlencode
from test_hotels_fast import functions

class RedirectTests(unittest.TestCase):
    def setUp(self):
        self.params=dict(ss='Petrópolis',checkin='2026-09-13',checkout='2026-09-14',group_adults=2,group_children=0,no_rooms=1)
        self.url='https://www.booking.com/searchresults.pt-br.html?'+urlencode(self.params)
        self.ns={}
        exec(functions('query_matches','open_confirmed_search'),self.ns)
    def test_parameters(self):
        match=self.ns['query_matches']
        self.assertTrue(match(self.url,self.params))
        self.assertTrue(match(self.url.replace('Petr%C3%B3polis','petropolis'),self.params))
        for url in [self.url.replace('2026-09-13','2026-09-09'),self.url+'&checkin=2026-09-13',self.url.replace('www.booking.com','example.com'),'https://www.booking.com/searchresults.pt-br.html?nflt=x']:
            self.assertFalse(match(url,self.params))
    def run_case(self,states):
        class Timeout(Exception): pass
        class Driver:
            def __init__(self):self.calls=0
            def get(d,url):
                d.current_url,d.cards=states[d.calls];d.calls+=1
            def find_elements(d,*a):return d.cards
        class Wait:
            def __init__(w,d,t):w.d=d
            def until(w,f):
                result=f(w.d)
                if not result:raise Timeout()
                return result
        mod=ModuleType('selenium.common.exceptions');mod.TimeoutException=Timeout
        self.ns.update(By=NS(CSS_SELECTOR='css'),WebDriverWait=Wait,fill_search_form=lambda driver,params:driver.get(self.url))
        d=Driver()
        with patch.dict(sys.modules,{'selenium.common.exceptions':mod}):
            try:result=self.ns['open_confirmed_search'](d,self.url,self.params)
            except RuntimeError as exc:result=exc
        return d.calls,result
    def test_redirect_restored_once(self):
        count,result=self.run_case([('https://www.booking.com/',[]),(self.url,[1])])
        self.assertEqual(count,2);self.assertEqual(result,[1])
    def test_redirect_persists_rejects_even_with_cards(self):
        count,result=self.run_case([('https://www.booking.com/',[1])]*2)
        self.assertEqual(count,2);self.assertIsInstance(result,RuntimeError)
    def test_correct_query_without_cards_no_retry(self):
        count,result=self.run_case([(self.url,[])])
        self.assertEqual(count,1);self.assertIsInstance(result,RuntimeError)
