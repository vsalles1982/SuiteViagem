import ast, re, unittest
from pathlib import Path
from types import SimpleNamespace
from suiteviagem.adapters.discovercars import search
from suiteviagem.history import History
from suiteviagem.web.server import command

class CarChoiceTests(unittest.TestCase):
    def test_ambiguous_and_exact_roundtrip(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scraper_carro/discovercars.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'LocalAmbiguo','normalizar_local','escolher_rotulo'}]
        ns={'re':re};exec(compile(ast.Module(body=nodes,type_ignores=[]),'motor','exec'),ns)
        options=[('Florianopolis Airport (FLN), Brazil','Florianopolis Airport'),('Florianopolis Downtown, Brazil','Florianopolis Downtown')]
        self.assertEqual(ns['escolher_rotulo'](options[0][0],options),options[0][0])
        def collect(*args):return ns['escolher_rotulo']('Florianópolis',options)
        with History(':memory:') as h:
            result=search(h,'Florianópolis','2026-09-13','2026-09-14',engine=SimpleNamespace(coletar_ofertas=collect),log=lambda x:None)
            self.assertEqual(result['results'],[])
            self.assertEqual(result['errors'][0]['location_options'],[x[0] for x in options])
            self.assertEqual(result['errors'][0]['code'],'location_choice_required')
            self.assertEqual(result,h.get(result['query_id']))
    def test_virtual_command_keeps_request(self):
        args=command(dict(module='cars',destination='Florianopolis Airport',start='2026-09-13',end='2026-09-14',limit=5),Path('/tmp/history.sqlite3'))
        self.assertEqual(args[0],'xvfb-run')
        self.assertIn('suiteviagem.carros_virtual',args)
        self.assertEqual(args[args.index('--local')+1],'Florianopolis Airport')
        self.assertIn('WAYLAND_DISPLAY',args)
