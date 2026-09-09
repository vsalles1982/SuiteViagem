"""Servidor local, execução isolada dos comandos e leitura do histórico."""
import argparse
from collections import deque
from datetime import date
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from uuid import UUID, uuid4
from suiteviagem.history import History

ROOT=Path(__file__).resolve().parents[2]
ASSETS=Path(__file__).resolve().parent

def command(data,db):
    module=data['module']
    def text(key,limit=150):
        v=data.get(key,'')
        if not isinstance(v,str) or not v.strip() or len(v)>limit or v.startswith('-'):raise ValueError('Campo inválido: '+key)
        return v.strip()
    def number(key,default,low,high):
        v=int(data.get(key,default))
        if not low<=v<=high:raise ValueError('Valor fora do intervalo: '+key)
        return str(v)
    if module=='flights':
        origin,dest=text('origin'),text('destination')
        if not all(re.fullmatch('[A-Za-z]{3}',v) for v in (origin,dest)) or origin.upper()==dest.upper():raise ValueError('Use códigos distintos de três letras.')
        args=['voos','--origem',origin,'--destino',dest,'--horizonte',number('horizon',7,5,365),'--intervalo',number('step',1,1,365)]
        if data.get('roundtrip') is True:args+=['--ida-volta','--duracao',number('duration',7,1,365)]
    elif module in {'hotels','cars','events'}:
        start,end=text('start'),text('end')
        if date.fromisoformat(end)<date.fromisoformat(start) or (module!='events' and end==start):raise ValueError('Confira a ordem das datas.')
        dest=text('destination')
        if module=='hotels':
            args=['hoteis_virtual','--destino',dest,'--checkin',start,'--checkout',end]
            if data.get('details_mode') != 'full':args.extend(['--rapido','--progressivo'])
        elif module=='cars':args=['carros_virtual','--local',dest,'--retirada',start,'--devolucao',end,'--limite',number('limit',5,1,100)]
        else:args=['shotgun','--cidade',dest,'--inicio',start,'--fim',end,'--limite',number('limit',5,1,50)]
    else:raise ValueError('Módulo desconhecido.')
    result=[sys.executable,'-u','-m','suiteviagem.'+args[0],*args[1:],'--db',str(db)]
    if module in {'hotels','cars'}:
        result=['xvfb-run','-a','-s','-screen 0 1920x1080x24 -nolisten tcp','env','-u','WAYLAND_DISPLAY','-u','WAYLAND_SOCKET',*result]
    return result

class Jobs:
    def __init__(self,db):
        self.db=db;self.lock=threading.RLock();self.job=None;self.process=None
    def state(self, preview_key=None):
        with self.lock:
            if not self.job:return None
            result={k:v for k,v in self.job.items() if k not in ('first_preview','preview','logs')}
            result.update(logs=list(self.job['logs']),elapsed=round((self.job.get('finished') or time.time())-self.job['started'],1))
            preview=self.job.get('preview')
            key=self.job['id']+':'+str(self.job.get('preview_version',0))
            result['preview']=None
            if preview is not None and preview_key!=key:
                result['preview']={**preview,'results':[
                    {**r,'details':{k:v for k,v in r.get('details',{}).items() if k!='source_record'}}
                    for r in preview['results']]}
            return result
    def start(self,data):
        cmd=command(data,self.db)
        if data['module'] in {'hotels','cars'} and not all(shutil.which(name) for name in ('xvfb-run','Xvfb','xauth')):
            raise ValueError('Display virtual indisponível. Instale xorg-server-xvfb e xorg-xauth.')
        with self.lock:
            if self.job and self.job['status'] in {'running','cancelling'}:raise ValueError('Uma busca está em andamento. Aguarde ou cancele antes de iniciar outra.')
            self.job={'id':str(uuid4()),'module':data['module'],'status':'running','started':time.time(),'query_id':None,'logs':deque(maxlen=180),'preview':None,'first_preview':None,'preview_version':0}
            try:
                self.process=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
            except Exception:
                self.job.update(status='failed',finished=time.time());raise
            threading.Thread(target=self._read,daemon=True).start()
            return self.state()
    def _read(self):
        proc=self.process
        for line in proc.stdout:
            line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',line).strip()
            if line.startswith('SUITE_PREVIEW:'):
                try:
                    payload=json.loads(line[len('SUITE_PREVIEW:'):])
                    with self.lock:
                        if payload['query_id']==self.job['query_id'] and payload['module']=='hotels':
                            self.job['preview']=payload
                            self.job['preview_version']+=1
                            if payload['results'] and self.job['first_preview'] is None:self.job['first_preview']=payload
                except (ValueError,KeyError,TypeError):pass
                continue
            if not line:continue
            with self.lock:
                self.job['logs'].append(line)
                match=re.search(r'(?:Consulta registrada|Histórico salvo): ([0-9a-f-]{36})',line)
                if match:self.job['query_id']=match[1]
        code=proc.wait()
        with self.lock:
            if self.job['status']=='cancelling' and self.job.get('first_preview'):
                first=self.job['first_preview']
                try:
                    with History(self.db) as history:
                        current=history.get(first['query_id'])
                        if current['status']=='running':
                            history.finish(first['query_id'],status='cancelled',results=first['results'],
                                coverage={'status':'partial','scope':'Primeiro lote conferido antes do cancelamento.',
                                          'limitations':['Coleta encerrada antecipadamente.'], 'metrics':[], 'stop_reason':'cancelled'},
                                warnings=['Primeiro lote preservado após encerramento do processo.'])
                except Exception as exc:
                    self.job['logs'].append('Não foi possível preservar o lote no histórico: '+str(exc))
        with self.lock:
            self.job.update(status='cancelled' if self.job['status']=='cancelling' else ('succeeded' if code==0 else 'failed'),finished=time.time())
    @staticmethod
    def _signal(proc, sig):
        try:os.killpg(proc.pid,sig)
        except ProcessLookupError:pass
    @staticmethod
    def _finish_cancel(proc, grace=8, terminate_grace=3):
        try:proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            Jobs._signal(proc,signal.SIGTERM)
            try:proc.wait(timeout=terminate_grace)
            except subprocess.TimeoutExpired:
                Jobs._signal(proc,signal.SIGKILL)
                proc.wait()
    def cancel(self):
        with self.lock:
            proc=self.process
            if proc and proc.poll() is None and self.job['status']!='cancelling':
                self.job['status']='cancelling'
                self._signal(proc,signal.SIGINT)
                threading.Thread(target=self._finish_cancel,args=(proc,),daemon=True).start()
            return self.state()
    def close(self):
        self.cancel()
        if self.process:self._finish_cancel(self.process)

def make_handler(db,jobs,token,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def allowed(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'}
        def send(self,data,status=200,kind='application/json; charset=utf-8',download=None):
            raw=json.dumps(data,ensure_ascii=False).encode() if kind.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if download:self.send_header('Content-Disposition',f'attachment; filename="{download}"')
            self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if not self.allowed():return self.send({'error':'Host não permitido'},403)
            path=urlparse(self.path).path
            try:
                if path=='/api/state':return self.send({'token':token,'job':jobs.state(parse_qs(urlparse(self.path).query).get('preview_key',[None])[0])})
                if path=='/api/history':
                    with History(db) as h:
                        rows=[]
                        for brief in h.list(limit=300):
                            q=h.get(brief['query_id'])
                            rows.append({**brief,'requested':q['requested'],'count':len(q['results']),'coverage':q['coverage']['status']})
                    return self.send(rows)
                if path.startswith('/api/query/'):
                    qid=path.split('/')[3];UUID(qid)
                    with History(db) as h:q=h.get(qid)
                    return self.send(q,download=f'consulta-{qid}.json' if path.endswith('/download') else None)
                static={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
                if path not in static:return self.send({'error':'Não encontrado'},404)
                filename,mime=static[path];return self.send((ASSETS/filename).read_bytes(),kind=mime)
            except (KeyError,ValueError):return self.send({'error':'Consulta não encontrada'},404)
            except Exception:return self.send({'error':'Não foi possível ler os dados locais.'},500)
        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Suite-Token')!=token or self.headers.get('Origin') not in {f'http://127.0.0.1:{port}',f'http://localhost:{port}'}:
                return self.send({'error':'Requisição não permitida'},403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:raise ValueError('Requisição inválida.')
                data=json.loads(self.rfile.read(size))
                if self.path=='/api/search':return self.send(jobs.start(data),202)
                if self.path=='/api/cancel':return self.send(jobs.cancel())
                return self.send({'error':'Não encontrado'},404)
            except (ValueError,KeyError,TypeError) as exc:return self.send({'error':str(exc)},400)
            except Exception:return self.send({'error':'Não foi possível iniciar a busca.'},500)
    return Handler

def main():
    p=argparse.ArgumentParser(description='Suíte de Viagens — interface web local')
    p.add_argument('--port',type=int,default=8765);p.add_argument('--db',type=Path,default=ROOT/'data/suiteviagem.sqlite3')
    a=p.parse_args()
    if not 1024<=a.port<=65535:p.error('Porta entre 1024 e 65535.')
    db=a.db.resolve()
    with History(db):pass
    jobs=Jobs(db)
    try:server=ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(db,jobs,secrets.token_urlsafe(32),a.port))
    except OSError as exc:p.exit(1,f'Não foi possível abrir a porta: {exc}\n')
    print(f'Suíte de Viagens: http://127.0.0.1:{a.port}\nCtrl+C encerra o servidor e sua busca ativa.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:jobs.close();server.server_close()
if __name__=='__main__':main()
