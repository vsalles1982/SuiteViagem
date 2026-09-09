import unittest,tempfile,zipfile
from pathlib import Path
from test_hotels_fast import functions
import xml.etree.ElementTree as E
from importlib.util import find_spec

class ExcelTests(unittest.TestCase):
    def test_exporters_preserve_values_and_literal_text(self):
        ns={};exec(functions('write_hotels_excel'),ns)
        rows=[{'Hotel Name':'=2+2','Price':123.45,'Address':None,'Hotel URL':'https://example.test'},
              {'Hotel Name':'Pousada São João','Price':190,'Address':'Rua 1','Extra':'texto'}]
        for engine in ('xlsxwriter','openpyxl'):
            if not find_spec(engine):continue
            with self.subTest(engine=engine),tempfile.TemporaryDirectory() as td:
                p=Path(td)/'out.xlsx';ns['write_hotels_excel'](p,rows,engine=engine)
                with zipfile.ZipFile(p) as z:
                    xml=E.fromstring(z.read('xl/worksheets/sheet1.xml'));n={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    self.assertEqual(len(xml.findall('.//x:row',n)),3)
                    self.assertEqual(xml.findall('.//x:f',n),[])
                    values=[v.text for v in xml.findall('.//x:v',n)]
                    self.assertIn('123.45',values);self.assertIn('190',values)
                    texts=''.join(xml.itertext());self.assertIn('=2+2',texts);self.assertIn('Pousada São João',texts);self.assertIn('Extra',texts)
