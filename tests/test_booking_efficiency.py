import json,re,tempfile,time
from pathlib import Path
from types import SimpleNamespace as NS
from collections import deque
from unittest.mock import patch
import unittest
from test_hotels_fast import functions
from suiteviagem.web.server import Jobs

class EfficiencyTests(unittest.TestCase):
    def test_driver_cache_checks_version_and_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'booking-hotel-scraper').mkdir();(root/'.wdm').mkdir()
            driver=root/'.wdm/driver';driver.write_text('fake')
            versions={'browser':'151.0.7922.173','driver':'151.0.7922.173'};calls=[]
            def output(args,**kw):return ('Chromium ' if args[0]=='/usr/bin/chromium' else 'ChromeDriver ')+versions['browser' if args[0]=='/usr/bin/chromium' else 'driver']
            def install():calls.append('install');versions['driver']=versions['browser'];return str(driver)
            ns={'__file__':str(root/'booking-hotel-scraper/hotels_booking.py'),'re':re,'ChromeType':NS(CHROMIUM='chromium'),'ChromeDriverManager':lambda **kw:NS(install=install)}
            exec(functions('resolve_chromedriver'),ns)
            with patch('pathlib.Path.home',return_value=root),patch('subprocess.check_output',side_effect=output):
                ns['resolve_chromedriver']();ns['resolve_chromedriver']();self.assertEqual(len(calls),1)
                versions['browser']='152.0.8000.10';ns['resolve_chromedriver']();self.assertEqual(len(calls),2)
                (root/'data/chromedriver-booking.json').write_text('invalid');ns['resolve_chromedriver']();self.assertEqual(len(calls),3)
    def test_state_omits_unchanged_preview_and_keeps_audit_copy(self):
        j=Jobs(Path('/tmp/unused'))
        preview={'results':[{'details':{'source_record':{'large':'audit'},'room':'room'}}]}
        j.job={'id':'a','started':time.time(),'logs':deque(),'first_preview':preview,'preview':preview,'preview_version':1}
        first=j.state();self.assertNotIn('source_record',first['preview']['results'][0]['details']);self.assertNotIn('first_preview',first)
        self.assertIsNone(j.state('a:1')['preview']);self.assertIsNotNone(j.state('other:1')['preview'])
        self.assertIn('source_record',j.job['first_preview']['results'][0]['details'])
    def test_batch_returns_same_snapshot_url(self):
        ns={'re':re,'NOT_INFORMED':'Não informado'}
        exec(functions('read_cards_batch','parse_price'),ns)
        d=NS(execute_script=lambda script:{'url':'https://www.booking.com/searchresults.html?checkin=2026-09-13','rows':[{'Hotel Name':'Hotel','Price Text':'R$ 123,45','Review Text':'Com nota 8,5'}]})
        rows,url=ns['read_cards_batch'](d)
        self.assertIn('checkin=2026-09-13',url);self.assertEqual(rows[0]['Price'],123.45);self.assertEqual(rows[0]['Review Score (/10)'],8.5)
