#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from parallel_arena_v3 import ProcessWorker, run_events

HOST = "127.0.0.1"
PORT = 8787

DEFAULTS = {
    "flight_origin": "RIO",
    "flight_dest": "SAO",
    "hotel_city": "Petrópolis",
    "car_location": "Sao Paulo Guarulhos Airport (GRU), Sao Paulo, Brazil",
    "event_city": "São Paulo",
    "start": "2026-09-20",
    "end": "2026-09-21",
    "limit": 5,
}

HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Suíte de Viagens — Live</title>
<style>
:root{--bg:#101218;--panel:#181b23;--text:#f4f6fb;--muted:#9ba4b4;--line:#2c3240;--accent:#a6ff4d}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 20% 0,#18202a 0,#101218 45%);color:var(--text);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:1180px;margin:auto;padding:28px}
header{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:22px}
h1{margin:0;font-size:34px;letter-spacing:-.03em}.suite{color:var(--accent)}
.badge{border:1px solid #33403d;background:#17231c;color:#bdfb84;border-radius:999px;padding:7px 12px;font-size:13px}
.search{background:#151821;border:1px solid var(--line);border-radius:20px;padding:18px;margin-bottom:20px}
.grid-form{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
label{display:block;color:var(--muted);font-size:12px;margin-bottom:6px}
input{width:100%;background:#0e1117;border:1px solid #32394a;border-radius:11px;color:white;padding:11px 12px;outline:none}
button{border:0;border-radius:12px;padding:12px 18px;background:var(--accent);color:#10150b;font-weight:800;cursor:pointer}
button:disabled{opacity:.45;cursor:not-allowed}
.actions{display:flex;align-items:center;gap:14px;margin-top:14px}.status{color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.card{min-height:220px;border-radius:18px;padding:16px;border:1px solid rgba(255,255,255,.09);overflow:hidden}
.card h2{margin:0 0 4px;font-size:16px}.card .time{font-size:27px;font-weight:800;margin:9px 0}.mini{color:rgba(255,255,255,.72);font-size:13px}
.flight{background:linear-gradient(145deg,#173b70,#102448)}
.hotel{background:linear-gradient(145deg,#56357f,#2e2147)}
.car{background:linear-gradient(145deg,#175c3e,#123a2b)}
.event{background:linear-gradient(145deg,#262932,#08090c)}
.result{margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.14);font-size:13px}
.event-list{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.14);max-height:118px;overflow-y:auto;overscroll-behavior:contain;padding-right:5px}
.event-list::-webkit-scrollbar{width:5px}
.event-list::-webkit-scrollbar-thumb{background:rgba(255,255,255,.22);border-radius:999px}
.event-item{padding:5px 1px;border-bottom:1px solid rgba(255,255,255,.07);font-size:11px;line-height:1.25;color:rgba(255,255,255,.78)}
.event-item:last-child{border-bottom:0}
.event-name{color:#fff;font-weight:650}
.event-meta{opacity:.68;font-size:10px;margin-top:1px}
.calc{margin-top:18px;background:linear-gradient(135deg,#d8b992,#9b744a);color:#251b12;border-radius:20px;padding:18px;display:grid;grid-template-columns:1fr auto;gap:20px;align-items:center}
.calc h2{margin:0}.total{font-size:36px;font-weight:900;white-space:nowrap}
.breakdown{margin-top:8px;font-size:13px;opacity:.82}
.progress{height:4px;background:#292f3b;border-radius:4px;overflow:hidden;margin-top:12px}.bar{height:100%;width:0;background:var(--accent);transition:width .35s}
@media(max-width:850px){.grid-form,.cards{grid-template-columns:1fr 1fr}}@media(max-width:520px){.grid-form,.cards{grid-template-columns:1fr}.calc{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<header>
 <div><div class="mini">LIVE SEARCH ENGINE</div><h1><span class="suite">Suíte</span> de Viagens</h1></div>
 <div id="readyBadge" class="badge">Aquecendo motores…</div>
</header>

<section class="search">
 <div class="grid-form">
  <div><label>Origem do voo</label><input id="fo" value="RIO"></div>
  <div><label>Destino do voo</label><input id="fd" value="SAO"></div>
  <div><label>Cidade do hotel</label><input id="hc" value="Petrópolis"></div>
  <div><label>Local do carro</label><input id="cl" value="Sao Paulo Guarulhos Airport (GRU), Sao Paulo, Brazil"></div>
  <div><label>Cidade dos eventos</label><input id="ec" value="São Paulo"></div>
  <div><label>Ida / check-in</label><input id="start" type="date" value="2026-09-20"></div>
  <div><label>Volta / check-out</label><input id="end" type="date" value="2026-09-21"></div>
  <div style="display:flex;align-items:end"><button id="go" disabled>Pesquisar ao vivo</button></div>
 </div>
 <div class="actions"><span id="status" class="status">Inicializando workers persistentes…</span></div>
 <div class="progress"><div id="bar" class="bar"></div></div>
</section>

<section class="cards">
 <article class="card flight"><h2>✈ Passagem</h2><div id="flightTime" class="time">—</div><div id="flightBody" class="mini">Aguardando pesquisa</div></article>
 <article class="card hotel"><h2>🛏 Hospedagem</h2><div id="hotelTime" class="time">—</div><div id="hotelBody" class="mini">Aguardando pesquisa</div></article>
 <article class="card car"><h2>🚗 Carro</h2><div id="carTime" class="time">—</div><div id="carBody" class="mini">Aguardando pesquisa</div></article>
 <article class="card event"><h2>🎟 Evento</h2><div id="eventTime" class="time">—</div><div id="eventBody" class="mini">Aguardando pesquisa</div></article>
</section>

<section class="calc">
 <div><h2>Calculadora da viagem</h2><div id="breakdown" class="breakdown">O total aparece quando os preços confirmados chegarem.</div></div>
 <div><div class="mini" style="color:#4f3926">MENOR TOTAL CONFIRMADO</div><div id="total" class="total">R$ —</div></div>
</section>
</div>

<script>
const $=id=>document.getElementById(id);
let ready=false, prices={flight:null,hotel:null,car:null,event:null};

function brl(v){return v==null?'—':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(v)}
function reset(){
 prices={flight:null,hotel:null,car:null,event:null};
 for(const k of ['flight','hotel','car','event']){$(k+'Time').textContent='…';$(k+'Body').textContent='consultando ofertas ao vivo…'}
 $('total').textContent='R$ —';$('breakdown').textContent='Somando apenas valores confirmados.';$('bar').style.width='8%';
}
function calc(){
 const items=[['Voo',prices.flight],['Hotel',prices.hotel],['Carro',prices.car],['Evento',prices.event]];
 const confirmed=items.filter(x=>typeof x[1]==='number' && x[1]>0);
 const sum=confirmed.reduce((a,x)=>a+x[1],0);
 $('total').textContent=confirmed.length?brl(sum):'R$ —';
 $('breakdown').textContent=items.map(([n,v])=>`${n}: ${v==null?'não incluído':brl(v)}`).join('  •  ');
}
function renderModule(r){
 const map={flights:'flight',hotels:'hotel',cars:'car',events:'event'}, k=map[r.module]; if(!k)return;
 $(k+'Time').textContent=(r.seconds??0).toFixed(2)+'s';
 if(!r.ok){$(k+'Body').innerHTML=`<b>Falhou</b><div class=result>${r.error||''}</div>`;return}
 if(k==='flight'){
   prices.flight=Number(r.price)||null;
   $(k+'Body').innerHTML=`Menor preço: <b>${brl(prices.flight)}</b><div class=result>${r.price_count||0} preços analisados</div>`;
 } else if(k==='hotel'){
   prices.hotel=Number(r.best_price)||null;
   const first=(r.top||[])[0];
   $(k+'Body').innerHTML=`${r.count||0} hospedagens<div class=result>${first?`${first.name}<br><b>${brl(first.total||first.price)}</b>`:'Sem preço confirmado'}</div>`;
 } else if(k==='car'){
   prices.car=Number(r.best_price)||null;
   const first=(r.top||[])[0];
   $(k+'Body').innerHTML=`${r.count||0} ofertas<div class=result>${first?`${first.name} · ${first.supplier}<br><b>${brl(first.price)}</b>`:'Sem preço confirmado'}</div>`;
 } else {
   const rows=(r.results||[]);
   const priced=rows
     .map(x=>Number(x.price))
     .filter(v=>Number.isFinite(v) && v>0);
   prices.event=priced.length?Math.min(...priced):null;

   const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
     '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
   }[c]));

   const list=rows.length
     ? rows.map((x,i)=>{
         const name=esc(x.name||x.title||`Evento ${i+1}`);
         const when=esc(x.date||x.datetime||x.start||'');
         const venue=esc(x.venue||x.place||x.location||'');
         const price=Number(x.price)>0?brl(Number(x.price)):'';
         const meta=[when,venue,price].filter(Boolean).join(' · ');
         return `<div class="event-item"><div class="event-name">${name}</div>${meta?`<div class="event-meta">${meta}</div>`:''}</div>`;
       }).join('')
     : `<div class="event-item">Nenhum evento confirmado no recorte atual${r.pages_scanned?` · ${r.pages_scanned} pág. verificadas`:''}</div>`;

   $(k+'Body').innerHTML=`${r.count||rows.length||0} evento(s)<div class="event-list">${list}</div>`;
 }
 calc();
}

async function pollReady(){
 try{
  const r=await fetch('/api/status'); const j=await r.json();
  ready=j.ready;
  $('readyBadge').textContent=ready?'Motores quentes ✓':(j.error?'Falha no warmup':'Aquecendo motores…');
  $('go').disabled=!ready;
  $('status').textContent=ready?'Pronto. Clique em “Pesquisar ao vivo”.':(j.stage||'Inicializando…');
 }catch(e){$('status').textContent='Servidor iniciando…'}
 if(!ready)setTimeout(pollReady,1000)
}
pollReady();

$('go').onclick=async()=>{
 reset(); $('go').disabled=true; $('status').textContent='Pesquisa ao vivo iniciada…';
 const payload={
  flight_origin:$('fo').value, flight_dest:$('fd').value, hotel_city:$('hc').value,
  car_location:$('cl').value,event_city:$('ec').value,start:$('start').value,end:$('end').value,limit:5
 };
 const resp=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const reader=resp.body.getReader(), dec=new TextDecoder(); let buf='', doneCount=0;
 while(true){
  const {value,done}=await reader.read(); if(done)break; buf+=dec.decode(value,{stream:true});
  let lines=buf.split('\n'); buf=lines.pop();
  for(const line of lines){if(!line.trim())continue; const ev=JSON.parse(line);
   if(ev.type==='module'){renderModule(ev.data);doneCount++;$('bar').style.width=(15+doneCount*20)+'%';}
   if(ev.type==='done'){$('status').textContent=`Busca concluída em ${ev.wall.toFixed(2)}s`; $('bar').style.width='100%';calc();}
   if(ev.type==='status')$('status').textContent=ev.message;
  }
 }
 $('go').disabled=false;
};
</script>
</body></html>'''

class EngineState:
    def __init__(self):
        self.workers = {}
        self.ready = False
        self.stage = "Inicializando workers persistentes…"
        self.error = None
        self.lock = threading.Lock()
        threading.Thread(target=self._boot, daemon=True).start()

    def _boot(self):
        try:
            for name in ("flights", "cars", "hotels"):
                self.stage = f"Subindo {name}…"
                self.workers[name] = ProcessWorker(name)
                self.workers[name].wait("READY", timeout=120)

            self.stage = "Aquecendo Flights…"
            self.workers["flights"].send({"op":"warm","origin":DEFAULTS["flight_origin"],
                                          "dest":DEFAULTS["flight_dest"],"start":DEFAULTS["start"]})
            self.workers["flights"].wait("WARM", timeout=120)

            self.stage = "Aquecendo Cars…"
            self.workers["cars"].send({"op":"warm"})
            self.workers["cars"].wait("WARM", timeout=120)

            self.stage = "Aquecendo Booking…"
            self.workers["hotels"].send({"op":"warm","city":DEFAULTS["hotel_city"],
                                         "start":DEFAULTS["start"],"end":DEFAULTS["end"]})
            self.workers["hotels"].wait("WARM", timeout=120)

            self.stage = "Assentando sessões…"
            time.sleep(3.0)
            self.ready = True
            self.stage = "Pronto"
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.stage = self.error

    def search(self, p, emit):
        if not self.ready:
            raise RuntimeError("Motores ainda não estão prontos.")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Já existe uma pesquisa em andamento.")
        executor = None
        try:
            t0 = time.monotonic()
            executor = ThreadPoolExecutor(max_workers=4)

            def wait_remote(name):
                try:
                    return self.workers[name].wait("DONE", timeout=120)
                except Exception as exc:
                    return {"module":name,"ok":False,"seconds":round(time.monotonic()-t0,3),
                            "error":f"{type(exc).__name__}: {exc}"}

            self.workers["flights"].send({"op":"search","origin":p["flight_origin"],
                                          "dest":p["flight_dest"],"start":p["start"]})
            emit({"type":"status","message":"✈ Chefão em pista livre…"})
            ff = executor.submit(wait_remote, "flights")

            flight_result = None
            try:
                flight_result = ff.result(timeout=9.0)
                gate = "flights_done"
            except FutureTimeout:
                gate = "gate_timeout_9s"

            ef = executor.submit(run_events, p["event_city"], p["start"], p["end"], int(p.get("limit",5)))

            self.workers["cars"].send({"op":"search","location":p["car_location"],
                                       "start":p["start"],"end":p["end"],"limit":int(p.get("limit",5))})
            cf = executor.submit(wait_remote, "cars")
            time.sleep(0.20)

            self.workers["hotels"].send({"op":"search","city":p["hotel_city"],
                                         "start":p["start"],"end":p["end"]})
            hf = executor.submit(wait_remote, "hotels")

            futures = {ff:"flights", ef:"events", cf:"cars", hf:"hotels"}
            sent = set()

            if flight_result is not None:
                emit({"type":"module","data":flight_result})
                sent.add("flights")

            for fut in as_completed(futures):
                name = futures[fut]
                if name in sent:
                    continue
                try:
                    r = fut.result()
                except Exception as exc:
                    r = {"module":name,"ok":False,"seconds":round(time.monotonic()-t0,3),
                         "error":f"{type(exc).__name__}: {exc}"}
                emit({"type":"module","data":r})
                sent.add(name)

            wall = round(time.monotonic()-t0,3)
            emit({"type":"done","wall":wall,"gate":gate})
        finally:
            if executor is not None:
                try:
                    executor.shutdown(wait=False, cancel_futures=False)
                except Exception:
                    pass
            self.lock.release()

STATE = EngineState()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/":
            raw=HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path=="/api/status":
            self._send_json({"ready":STATE.ready,"stage":STATE.stage,"error":STATE.error})
            return
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path!="/api/search":
            self.send_error(404)
            return
        try:
            n=int(self.headers.get("Content-Length","0"))
            p=json.loads(self.rfile.read(n) or b"{}")
            for k,v in DEFAULTS.items():
                p.setdefault(k,v)

            self.send_response(200)
            self.send_header("Content-Type","application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control","no-cache")
            self.send_header("Connection","close")
            self.end_headers()

            def emit(obj):
                self.wfile.write((json.dumps(obj,ensure_ascii=False,default=str)+"\n").encode())
                self.wfile.flush()

            STATE.search(p, emit)
        except Exception as exc:
            try:
                self.wfile.write((json.dumps({"type":"error","error":f"{type(exc).__name__}: {exc}"},ensure_ascii=False)+"\n").encode())
                self.wfile.flush()
            except Exception:
                pass

def main():
    print("="*72)
    print(" SUÍTE DE VIAGENS — WEB v3.7 CHAMPION")
    print("="*72)
    print(f"Abra no navegador: http://{HOST}:{PORT}")
    print("A página ficará pronta quando os três workers terminarem o warmup.")
    httpd=ThreadingHTTPServer((HOST,PORT),Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        for w in STATE.workers.values():
            try:
                w.close()
            except Exception:
                pass

if __name__=="__main__":
    main()
