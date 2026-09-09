import ast,re,unittest
from pathlib import Path
from types import SimpleNamespace

class CalendarTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scraper_carro/discovercars.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'fase_calendario','texto_busca_local','normalizar_local'}]
        self.ns={'re':re,'By':SimpleNamespace(CSS_SELECTOR='css')}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'motor','exec'),self.ns)
    def test_desktop_phase_and_closed(self):
        cal=SimpleNamespace(find_elements=lambda *a:[])
        fields=[SimpleNamespace(get_attribute=lambda a:'DatePicker-CalendarField DatePicker-CalendarField_isActive'),SimpleNamespace(get_attribute=lambda a:'DatePicker-CalendarField')]
        visible=lambda css:[cal] if css=='.rdrCalendarWrapper' else fields
        phase=self.ns['fase_calendario'];self.assertTrue(phase(visible,'Early'));self.assertFalse(phase(visible,'Continuous'))
        fields.reverse();self.assertTrue(phase(visible,'Continuous'));self.assertFalse(phase(visible,'Early'))
        self.assertFalse(phase(lambda css:[],'Early'))
    def test_compact_overrides_desktop_field(self):
        cal=SimpleNamespace(find_elements=lambda by,css:[1] if css=='.rdrDateDisplayItem' or 'Continuous' in css else [])
        fields=[SimpleNamespace(get_attribute=lambda a:'DatePicker-CalendarField_isActive')]*2
        visible=lambda css:[cal] if css=='.rdrCalendarWrapper' else fields
        self.assertTrue(self.ns['fase_calendario'](visible,'Continuous'))
        self.assertFalse(self.ns['fase_calendario'](visible,'Early'))
    def test_airport_query_preserves_addresses(self):
        fn=self.ns['texto_busca_local']
        self.assertEqual(fn('Florianopolis Airport (FLN), Florianopolis, Brazil'),'Florianopolis Airport (FLN)')
        address='Rod. Ac. ao Aeroporto, 6.200 - Carianos, Brazil'
        self.assertEqual(fn(address),address)
