import http.client,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from suiteviagem.web.server import command,make_handler
from suiteviagem.history import History
from suiteviagem.demo import run
class WebTests(unittest.TestCase):
    def test_commands(self):
        for m in ('events','cars','hotels'):
            c=command({'module':m,'destination':'São Paulo','start':'2026-09-12','end':'2026-09-13'},Path('/tmp/db'))
            self.assertIn('São Paulo',c)
        self.assertIn('--ida-volta',command({'module':'flights','origin':'RIO','destination':'SAO','roundtrip':True},Path('/tmp/db')))
        with self.assertRaises(ValueError):command({'module':'invalid'},Path('/tmp/db'))
    def test_http_and_protection(self):
        class Jobs:
            def state(self,preview_key=None):return None
            def start(self,data):return {'id':'test'}
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'db'
            with History(db) as h:ids=run(h)
            server=ThreadingHTTPServer(('127.0.0.1',0),lambda *a:None);port=server.server_port
            server.RequestHandlerClass=make_handler(db,Jobs(),'token',port)
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            def req(method,path,headers=None,body=None):
                c=http.client.HTTPConnection('127.0.0.1',port);c.request(method,path,body=body,headers=headers or {})
                r=c.getresponse();raw=r.read();status=r.status;c.close();return status,raw
            try:
                status,raw=req('GET','/api/state?preview_key=abc%3A1');self.assertEqual(status,200);self.assertEqual(json.loads(raw)['token'],'token')
                status,raw=req('GET','/api/history');self.assertEqual(status,200);self.assertEqual(len(json.loads(raw)),4)
                status,raw=req('GET','/api/query/'+ids[0]);self.assertEqual(json.loads(raw)['query_id'],ids[0])
                self.assertEqual(req('GET','/',{'Host':'evil.test'})[0],403)
                self.assertEqual(req('POST','/api/search',body='{}')[0],403)
                headers={'Origin':f'http://127.0.0.1:{port}','X-Suite-Token':'token','Content-Type':'application/json'}
                self.assertEqual(req('POST','/api/search',headers,'{"module":"hotels"}')[0],202)
                self.assertEqual(req('GET','/../../etc/passwd')[0],404)
            finally:server.shutdown();server.server_close();t.join()
