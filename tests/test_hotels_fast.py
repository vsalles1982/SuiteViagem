import ast,re,tempfile,os,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from suiteviagem.web.server import command

def functions(*names):
    p=Path(__file__).resolve().parents[1]/'booking-hotel-scraper/hotels_booking.py'
    tree=ast.parse(p.read_text())
    return compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(p),'exec')
class FastHotelsTests(unittest.TestCase):
    def test_web_modes(self):
        d={'module':'hotels','destination':'Petrópolis','start':'2026-09-13','end':'2026-09-14'}
        c=command(d,Path('/tmp/db'));self.assertIn('xvfb-run',c);self.assertNotIn('--oculto',c);self.assertIn('--rapido',c)
        d['details_mode']='full';c=command(d,Path('/tmp/db'));self.assertIn('xvfb-run',c);self.assertNotIn('--oculto',c);self.assertNotIn('--rapido',c)
    def test_headless(self):
        class Options:
            def __init__(self):self.args=[]
            def add_argument(self,a):self.args.append(a)
            def add_experimental_option(self,*a):pass
        ns={'resolve_chromedriver':lambda:'driver','webdriver':NS(ChromeOptions=Options,Chrome=lambda **kw:kw['options']),'ChromeService':lambda x:x,
            'ChromeDriverManager':lambda **kw:NS(install=lambda:'driver'),'ChromeType':NS(CHROMIUM='chrome')}
        exec(functions('create_driver'),ns)
        self.assertIn('--headless=new',ns['create_driver'](True).args)
        self.assertNotIn('--headless=new',ns['create_driver'](False).args)
    def test_fast_skips_details(self):
        class Column:
            def notna(self):return self
            def sum(self):return 1
            def __ne__(self,x):return self
        class Frame:
            def sort_values(self,*a,**k):return self
            def __getitem__(self,k):return Column()
            def __len__(self):return 1
            def to_excel(self,p,**kw):Path(p).write_bytes(b'test')
        rows=[{'Hotel Name':'Teste','Hotel URL':'https://example.test','Price':10,'Currency':'BRL','Taxes Text':'Impostos e taxas incluídos'}]
        calls=[];driver=NS(current_url='https://www.booking.com/',set_page_load_timeout=lambda n:None,get=lambda u:None,quit=lambda:calls.append('quit'))
        def forbidden(*a):raise AssertionError('Não deve abrir detalhes')
        ns={'write_hotels_excel':lambda path,rows:Path(path).write_bytes(b'test'),'open_confirmed_search':lambda *a:True,'query_matches':lambda *a:True,'re':re,'time':__import__('time'),'NOT_INFORMED':'Não informado','REFERENCE_COORDS':None,'validate_search':lambda *a:1,
            'is_petropolis':lambda d:False,'create_driver':lambda **kw:driver,'WebDriverWait':lambda *a:NS(until=lambda f:True),
            'EC':NS(presence_of_element_located=lambda x:True),'By':NS(XPATH='xpath'),'extract_hotels':lambda *a,**k:rows,
            'fetch_details':forbidden,'price_with_taxes':lambda *a:(0,10,'incluídos'),'pd':NS(DataFrame=lambda rows:Frame())}
        exec(functions('run_scraping'),ns);cwd=os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            try:
                os.chdir(td);r=ns['run_scraping']('Petrópolis','2026-09-13','2026-09-14',fast=True,headless=True,return_records=True)
            finally:os.chdir(cwd)
        self.assertEqual(r['records'][0]['Address'],'Não informado');self.assertIn('cards_seconds',r['timings']);self.assertEqual(calls,['quit'])
