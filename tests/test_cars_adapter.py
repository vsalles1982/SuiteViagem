import ast, base64, json
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
import unittest
from suiteviagem.adapters.discovercars import search, normalize
from suiteviagem.history import History

DATA={'PickupLocationId':1741,'DropOffLocationId':1741,'PickupDateTime':'2026-09-12T11:00:00','DropOffDateTime':'2026-09-13T11:00:00','ResidenceCountry':'BR','DriverAge':35}
def engine():
    # Exercitar os validadores reais sem exigir navegador nos testes locais.
    tree=ast.parse((Path(__file__).resolve().parents[1]/'scraper_carro/discovercars.py').read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'ler_consulta','identidade'}]
    ns={}
    exec('import base64,json,re\nfrom datetime import datetime\nfrom urllib.parse import urlparse,parse_qs',ns)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'motor','exec'),ns)
    row={'Modelo':'Toyota Aygo','Moeda':'BRL','TotalBRL':Decimal('189.67'),'Link':'https://www.discovercars.com/offer/test?sq='+base64.b64encode(json.dumps(DATA).encode()).decode(),
         'Retirada':DATA['PickupDateTime'],'Devolucao':DATA['DropOffDateTime'],'LocalRetiradaId':1741,'LocalDevolucaoId':1741,'Residencia':'BR','Idade':35,
         'ColetadoEm':'2026-09-08T10:00:00-03:00','CoberturaAdicional':'Não incluída','Locadora':'Teste'}
    report={'consulta':DATA.copy(),'resultados':[row],'erros':[],'motivo':'result_limit','ofertas_coletadas':1}
    return SimpleNamespace(ler_consulta=ns['ler_consulta'],identidade=ns['identidade'],coletar_ofertas=lambda *a:report),row
class CarsTests(unittest.TestCase):
    def test_roundtrip(self):
        e,row=engine()
        with History(':memory:') as h:
            r=search(h,'Ibiza Airport','2026-09-12','2026-09-13',1,engine=e,log=lambda m:None)
            self.assertEqual(r['status'],'succeeded')
            self.assertEqual(h.get(r['query_id']),r)
            price=r['results'][0]['price']
            self.assertEqual(price['amount_minor'],18967)
            self.assertIsNone(price['total_minor'])
            self.assertFalse(price['optional_coverage_included'])
    def test_mismatch(self):
        e,row=engine()
        row['Idade']=40
        with self.assertRaises(ValueError):normalize(row,'test',e,DATA)
    def test_currency(self):
        e,row=engine()
        row['Moeda']='EUR'
        with self.assertRaises(ValueError):normalize(row,'test',e,DATA)
    def test_failure_cancel(self):
        for exception,status in [(RuntimeError,'failed'),(KeyboardInterrupt,'cancelled')]:
            e,row=engine()
            def fail(*args):raise exception('interrompido')
            e.coletar_ofertas=fail
            with History(':memory:') as h:
                r=search(h,'Ibiza Airport','2026-09-12','2026-09-13',1,engine=e,log=lambda m:None)
                self.assertEqual(r['status'],status)
                self.assertEqual(h.get(r['query_id']),r)
