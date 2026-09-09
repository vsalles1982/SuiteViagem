import sys
import unittest
from types import SimpleNamespace as NS, ModuleType
from unittest.mock import patch
from test_hotels_fast import functions

class FormTests(unittest.TestCase):
    def run_form(self,clear_destination=False,disabled=False,bad_dates=False):
        state={'open':False,'selected':set(),'value':'','submitted':False,'writes':0}
        params=dict(ss='Petrópolis',checkin='2026-09-13',checkout='2026-09-14')
        class E:
            def __init__(self,kind):self.kind=kind
            def is_displayed(self):return True
            def is_enabled(self):return True
            def get_attribute(self,name):
                if name=='aria-expanded':return str(state['open']).lower()
                if name=='aria-disabled':return str(disabled).lower()
                if name=='aria-checked':return str(self.kind in state['selected'] and not bad_dates).lower()
                if name=='value':return state['value']
            def click(self):
                if self.kind=='calendar':state['open']=not state['open']
                elif self.kind=='submit':state['submitted']=True
                elif self.kind.startswith('2026'):state['selected'].add(self.kind)
            def send_keys(self,*args):
                if args==('BACKSPACE',):state['value']=''
                if args==(params['ss'],):
                    state['writes']+=1;state['value']='' if clear_destination else params['ss']
        class D:
            def find_elements(self,by,selector):
                if selector=='[data-testid="searchbox-dates-container"]':return [E('calendar')]
                if selector=='input[name="ss"]':return [E('input')]
                if 'button[type="submit"]' in selector:return [E('submit')]
                if selector=='[data-date]':return [E(params['checkin'])] if state['open'] else []
                if selector.startswith('[data-date="'):return [E(selector.split('"')[1])] if state['open'] else []
                return []
        class W:
            def __init__(self,*a):pass
            def until(self,f):
                r=f(D())
                if not r:raise AssertionError('Condição do formulário não atendida')
                return r
        keys=ModuleType('selenium.webdriver.common.keys');keys.Keys=NS(CONTROL='CONTROL',BACKSPACE='BACKSPACE',ESCAPE='ESCAPE',TAB='TAB')
        exceptions=ModuleType('selenium.common.exceptions');exceptions.TimeoutException=TimeoutError
        ns={'By':NS(CSS_SELECTOR='css'),'WebDriverWait':W,'time':NS(sleep=lambda t:None)}
        exec(functions('fill_search_form'),ns)
        with patch.dict(sys.modules,{'selenium.webdriver.common.keys':keys,'selenium.common.exceptions':exceptions}):
            try:ns['fill_search_form'](D(),params);error=None
            except RuntimeError as exc:error=exc
        return state,error
    def test_fills_and_submits(self):
        s,e=self.run_form();self.assertIsNone(e);self.assertTrue(s['submitted']);self.assertEqual(len(s['selected']),2)
    def test_cleared_destination_never_submits(self):
        s,e=self.run_form(clear_destination=True);self.assertIsNotNone(e);self.assertFalse(s['submitted']);self.assertEqual(s['writes'],2)
    def test_disabled_date_never_submits(self):
        s,e=self.run_form(disabled=True);self.assertIsNotNone(e);self.assertFalse(s['submitted'])
    def test_unconfirmed_dates_never_submits(self):
        s,e=self.run_form(bad_dates=True);self.assertIsNotNone(e);self.assertFalse(s['submitted'])
