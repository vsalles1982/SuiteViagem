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
    "start": "2026-11-07",
    "end": "2026-11-08",
    "limit": 5,
}

HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07121f">
<title>Suíte de Viagens — Live</title>
<style>
:root{
  --bg:#07111d;--bg2:#0b1624;--panel:#0f1c2b;--panel2:#122337;
  --text:#f5f8ff;--muted:#98a9be;--line:rgba(164,196,232,.16);
  --accent:#9cff57;--accent2:#55ed8a;--blue:#258cff;--violet:#b84cff;
  --green:#21c66b;--pink:#ff5c9e;--gold:#f0bd68;--danger:#ff7373;
  --shadow:0 18px 50px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{
  margin:0;min-height:100vh;color:var(--text);
  font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:
    radial-gradient(circle at 78% -8%,rgba(37,140,255,.16),transparent 34%),
    radial-gradient(circle at 15% 12%,rgba(156,255,87,.07),transparent 25%),
    linear-gradient(180deg,#06111d 0%,#08131f 55%,#06101a 100%);
}
button,input{font:inherit}
button{cursor:pointer}
.shell{width:min(1480px,calc(100% - 32px));margin:0 auto;padding:28px 0 36px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:20px}
.brand{display:flex;align-items:center;gap:14px;min-width:0}
.brand-mark{
  width:52px;height:52px;display:grid;place-items:center;border-radius:16px;
  background:linear-gradient(145deg,#0e315b,#0d1d35);
  border:1px solid rgba(65,158,255,.55);font-size:28px;box-shadow:0 10px 35px rgba(35,122,255,.18)
}
.brand-copy h1{font-size:clamp(26px,3vw,42px);line-height:1;margin:0;font-weight:850;letter-spacing:-.04em}
.brand-copy h1 span{background:linear-gradient(90deg,#b3ff6e,#58ee8b);-webkit-background-clip:text;background-clip:text;color:transparent}
.brand-copy p{margin:6px 0 0;color:var(--muted);font-size:13px}
.engine-badge{
  display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:16px;
  border:1px solid rgba(75,226,128,.35);background:rgba(12,50,35,.72);
  color:#dfffd1;box-shadow:0 10px 30px rgba(0,0,0,.18)
}
.engine-dot{width:9px;height:9px;border-radius:50%;background:#42f08b;box-shadow:0 0 14px #42f08b}
.engine-badge small{display:block;color:#8fd5ae;font-size:11px;margin-top:1px}
.hero{
  position:relative;overflow:hidden;border:1px solid var(--line);border-radius:28px;
  background:
    radial-gradient(circle at 100% 0,rgba(49,129,212,.18),transparent 30%),
    linear-gradient(145deg,rgba(13,31,49,.96),rgba(8,19,31,.96));
  box-shadow:var(--shadow);padding:24px;
}
.hero::after{
  content:"✈";position:absolute;right:4%;top:-28px;font-size:180px;opacity:.045;transform:rotate(-12deg);pointer-events:none
}
.hero-head{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:18px;position:relative;z-index:1}
.hero-title{display:flex;gap:12px;align-items:flex-start}
.hero-icon{width:46px;height:46px;border-radius:15px;background:#0d325e;border:1px solid rgba(59,154,255,.45);display:grid;place-items:center;font-size:24px}
.hero h2{font-size:22px;margin:1px 0 2px;letter-spacing:-.02em}
.hero-head p{margin:0;color:var(--muted)}
.hero-pill{padding:9px 12px;border-radius:999px;background:rgba(255,255,255,.035);border:1px solid var(--line);color:#cbd8e7;font-size:12px;white-space:nowrap}
.form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;position:relative;z-index:1}
.field{min-width:0}
.field label{display:block;color:#b8c7d9;font-size:12px;margin:0 0 6px}
.input-wrap{position:relative}
.input-wrap .ico{position:absolute;left:13px;top:50%;transform:translateY(-50%);font-size:16px;opacity:.85;pointer-events:none}
.input-wrap input{
  width:100%;height:48px;padding:0 13px 0 40px;border-radius:13px;color:#eef5ff;
  background:linear-gradient(180deg,rgba(19,38,59,.92),rgba(13,28,44,.92));
  border:1px solid rgba(122,171,225,.28);outline:none;transition:.2s;
}
.input-wrap input:focus{border-color:rgba(156,255,87,.58);box-shadow:0 0 0 3px rgba(156,255,87,.08)}
.input-wrap input[type="date"]{color-scheme:dark}
.search-action{display:flex;align-items:flex-end;flex-wrap:wrap;gap:10px;grid-column:1/-1}
.search-action button{flex:1 1 220px;min-width:0}
#tripLink{min-height:48px;padding:10px 14px;border:1px solid var(--line);border-radius:14px;background:var(--panel2);color:var(--text);font-weight:750}
#tripLink:disabled{opacity:.65;cursor:wait}
#tripLink:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
#go{
  height:48px;border:0;border-radius:14px;font-weight:850;font-size:16px;color:#07140b;
  background:linear-gradient(90deg,#6cf686,#b3ff62);
  box-shadow:0 12px 30px rgba(108,246,134,.16);transition:.18s transform,.18s opacity;
}
#go:hover:not(:disabled){transform:translateY(-1px)}
#go:disabled{opacity:.42;cursor:not-allowed;transform:none}
.search-status{
  display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:center;
  margin-top:14px;padding:11px 14px;border-radius:16px;border:1px solid rgba(82,237,142,.22);
  background:linear-gradient(90deg,rgba(12,52,38,.65),rgba(12,30,43,.68));
}
.status-icon{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:#54e98d;color:#062613;font-weight:900}
#status{color:#dce8f3;font-size:13px;white-space:nowrap}
.progress{height:6px;background:#183042;border-radius:999px;overflow:hidden}
.bar{height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,#58ef8c,#b4ff63);transition:width .35s ease}
.status-note{color:#8398ad;font-size:11px;white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:16px}
.card{
  position:relative;overflow:hidden;min-height:290px;border-radius:24px;padding:18px;
  border:1px solid rgba(255,255,255,.13);box-shadow:0 16px 34px rgba(0,0,0,.18)
}
.card::after{content:"";position:absolute;inset:auto -30px -45px auto;width:160px;height:160px;border-radius:50%;filter:blur(6px);opacity:.18}
.flight{background:linear-gradient(145deg,#0f64bc,#0c274b)}.flight::after{background:#67b7ff}
.hotel{background:linear-gradient(145deg,#7130a4,#321849)}.hotel::after{background:#ff78ed}
.car{background:linear-gradient(145deg,#08763f,#073c27)}.car::after{background:#5bff9e}
.event{background:linear-gradient(145deg,#171d27,#090d13)}.event::after{background:#ff5c9e}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;position:relative;z-index:1}
.card-label{display:flex;gap:10px;align-items:center}
.card-icon{width:38px;height:38px;border-radius:12px;background:rgba(255,255,255,.1);display:grid;place-items:center;font-size:20px}
.card h3{margin:0;font-size:18px}
.card-sub{color:rgba(255,255,255,.68);font-size:12px;margin-top:2px}
.time{
  padding:6px 9px;border-radius:999px;border:1px solid rgba(255,255,255,.28);
  background:rgba(4,13,23,.23);font-weight:800;font-size:13px;white-space:nowrap
}
.card-body{margin-top:22px;position:relative;z-index:1}
.metric-label{color:rgba(255,255,255,.7);font-size:12px}
.metric-value{font-size:30px;font-weight:900;letter-spacing:-.035em;margin-top:2px}
.detail-box{margin-top:18px;padding-top:14px;border-top:1px solid rgba(255,255,255,.16);color:rgba(255,255,255,.82);font-size:13px}
.detail-box b{color:white}
.see-all{position:relative;z-index:1;margin-top:16px;padding:9px 13px;border:1px solid rgba(255,255,255,.35);border-radius:10px;background:rgba(0,0,0,.18);color:var(--text)}
.see-all:disabled{opacity:.45;cursor:not-allowed}
.see-all:focus-visible,.details-close:focus-visible,.details-list a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.details-modal{width:min(720px,calc(100% - 24px));max-height:85vh;max-height:85dvh;padding:0;border:1px solid var(--line);border-radius:20px;background:var(--panel);color:var(--text);box-shadow:var(--shadow);overflow:auto}
.details-modal::backdrop{background:rgba(0,0,0,.72)}
body:has(.details-modal[open]){overflow:hidden}
.details-head{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 20px;background:var(--panel);border-bottom:1px solid var(--line)}
.details-head h2{margin:0;font-size:20px}
.details-close{flex-shrink:0;width:44px;height:44px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--text);font-size:26px}
.details-note{margin:16px 20px;color:var(--muted);font-size:13px}
.details-list{list-style:none;margin:0;padding:0 20px 20px}
.details-list li{padding:16px 0;border-top:1px solid var(--line);overflow-wrap:anywhere}
.details-list h3{margin:0;font-size:16px}
.details-meta{margin:5px 0;color:var(--muted);font-size:13px}
.details-price{margin:8px 0;font-weight:800}
.details-list a{display:inline-block;padding:6px 0;color:var(--accent);text-underline-offset:3px}
.event .card-body{margin-top:12px}
.event-list{margin-top:10px;max-height:172px;overflow-y:auto;overscroll-behavior:contain;padding-right:6px}
.event-list::-webkit-scrollbar{width:5px}
.event-list::-webkit-scrollbar-track{background:rgba(255,255,255,.04);border-radius:99px}
.event-list::-webkit-scrollbar-thumb{background:rgba(255,255,255,.28);border-radius:99px}
.event-item{padding:8px 2px;border-bottom:1px solid rgba(255,255,255,.09);font-size:11px;line-height:1.28;color:#bac6d3}
.event-name{color:#fff;font-size:12px;font-weight:750}
.event-meta{opacity:.72;font-size:10px;margin-top:3px}
.card.loading .card-body{opacity:.65}
.skeleton{height:9px;border-radius:999px;background:linear-gradient(90deg,rgba(255,255,255,.06),rgba(255,255,255,.16),rgba(255,255,255,.06));background-size:200% 100%;animation:shimmer 1.2s linear infinite;margin:10px 0}
@keyframes shimmer{to{background-position:-200% 0}}
.calc{
  margin-top:16px;padding:18px 20px;border-radius:24px;color:#24180b;
  background:
    radial-gradient(circle at 90% 0,rgba(255,255,255,.28),transparent 24%),
    linear-gradient(135deg,#efca87,#bd8745);
  box-shadow:0 16px 38px rgba(0,0,0,.18);
  display:grid;grid-template-columns:minmax(230px,1.1fr) 2fr auto;gap:24px;align-items:center
}
.calc-title{display:flex;align-items:center;gap:12px}
.calc-icon{width:44px;height:44px;border-radius:13px;background:#1a1914;color:#f6c96e;display:grid;place-items:center;font-size:22px}
.calc h2{margin:0;font-size:19px}
.calc p{margin:2px 0 0;font-size:12px;opacity:.75}
.breakdown{display:flex;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;font-size:12px}
.cost-chip{padding:7px 9px;border-radius:10px;background:rgba(72,43,11,.08);white-space:nowrap}
.total-wrap{padding:10px 14px;border-radius:16px;background:rgba(255,241,198,.55);border:1px solid rgba(76,45,12,.12);min-width:230px}
.total-label{font-size:10px;font-weight:800;letter-spacing:.05em}
.total{font-size:32px;line-height:1.1;font-weight:950;letter-spacing:-.04em;margin-top:2px;white-space:nowrap}
.mobile-nav{display:none}
@media(max-width:1050px){
  .form-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
  .calc{grid-template-columns:1fr 1.4fr}.total-wrap{grid-column:1/-1}
}
@media(max-width:680px){
  body{padding-bottom:76px}
  .shell{width:min(100% - 18px,620px);padding:14px 0 24px}
  .topbar{align-items:flex-start;margin-bottom:12px}
  .brand{gap:10px}.brand-mark{width:42px;height:42px;border-radius:13px;font-size:23px}
  .brand-copy h1{font-size:25px}.brand-copy p{font-size:11px;max-width:220px}
  .engine-badge{padding:8px 10px;border-radius:13px;font-size:11px}.engine-badge small{display:none}
  .hero{border-radius:21px;padding:14px}
  .hero-head{margin-bottom:13px}.hero-icon{display:none}.hero h2{font-size:17px}.hero-head p{font-size:11px}.hero-pill{display:none}
  .form-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
  .field label{font-size:11px}.input-wrap input{height:44px;font-size:14px;padding-left:36px}.input-wrap .ico{left:11px}
  .search-action{grid-column:1/-1}.search-action #go{height:48px}
  .search-status{grid-template-columns:auto 1fr;gap:10px;padding:9px 10px}.status-note{display:none}.progress{grid-column:2}
  #status{font-size:11px;overflow:hidden;text-overflow:ellipsis}
  .cards{grid-template-columns:1fr;gap:10px;margin-top:10px}
  .card{min-height:0;border-radius:18px;padding:14px}
  .card::after{width:120px;height:120px}
  .card-head{align-items:center}.card-icon{width:34px;height:34px;border-radius:10px}
  .card h3{font-size:16px}.card-sub{font-size:11px}.time{font-size:12px;padding:5px 8px}
  .card-body{margin-top:12px}.metric-value{font-size:24px}.detail-box{margin-top:10px;padding-top:10px}
  .event-list{max-height:150px}
  .calc{grid-template-columns:1fr;padding:14px;border-radius:19px;gap:12px}
  .calc-title{align-items:flex-start}.breakdown{justify-content:flex-start;gap:6px}.cost-chip{font-size:11px}
  .total-wrap{min-width:0;width:100%}.total{font-size:29px}
  .mobile-nav{
    display:grid;grid-template-columns:repeat(3,1fr);position:fixed;z-index:50;left:10px;right:10px;bottom:8px;
    max-width:610px;margin:auto;padding:7px;border-radius:19px;background:rgba(7,19,31,.92);
    border:1px solid var(--line);backdrop-filter:blur(16px);box-shadow:0 12px 30px rgba(0,0,0,.35)
  }
  .mobile-nav button{
    min-height:48px;border:0;background:transparent;color:#7f91a4;border-radius:13px;font-size:11px
  }
  .mobile-nav button.active{color:#9cff57;background:rgba(156,255,87,.08)}
}
@media(max-width:430px){
  .form-grid{grid-template-columns:1fr}
  .search-action{grid-column:auto}
  .engine-badge{max-width:132px}
  .engine-badge span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark">✈️</div>
      <div class="brand-copy">
        <h1>Suíte de <span>Viagens</span></h1>
        <p>Passagens, hotéis, carros e eventos em uma única busca.</p>
        <p>Sem cadastro, sem email… gere seu link e voe!</p>
      </div>
    </div>
    <div class="engine-badge" id="readyBadge">
      <span class="engine-dot"></span>
      <span><b>Aquecendo motores…</b><small>Preparando os módulos</small></span>
    </div>
  </header>

  <main>
    <section class="hero">
      <div class="hero-head">
        <div class="hero-title">
          <div class="hero-icon">⌕</div>
          <div>
            <h2>Planeje sua próxima viagem</h2>
            <p>Uma busca ao vivo. Quatro módulos especializados.</p>
          </div>
        </div>
        <div class="hero-pill">⚡ Uma busca. Mil possibilidades.</div>
      </div>

      <div class="form-grid">
        <div class="field">
          <label for="fo">Origem do voo</label>
          <div class="input-wrap"><span class="ico">✈</span><input id="fo" value="RIO" autocomplete="off"></div>
        </div>
        <div class="field">
          <label for="fd">Destino do voo</label>
          <div class="input-wrap"><span class="ico">✈</span><input id="fd" value="SAO" autocomplete="off"></div>
        </div>
        <div class="field">
          <label for="hc">Cidade do hotel</label>
          <div class="input-wrap"><span class="ico">🛏</span><input id="hc" value="Petrópolis" autocomplete="off"></div>
        </div>
        <div class="field">
          <label for="cl">Local do carro</label>
          <div class="input-wrap"><span class="ico">🚗</span><input id="cl" value="Sao Paulo Guarulhos Airport (GRU), Sao Paulo, Brazil" autocomplete="off"></div>
        </div>
        <div class="field">
          <label for="ec">Cidade dos eventos</label>
          <div class="input-wrap"><span class="ico">🎟</span><input id="ec" value="São Paulo" autocomplete="off"></div>
        </div>
        <div class="field">
          <label for="start">Ida / check-in</label>
          <div class="input-wrap"><span class="ico">▣</span><input id="start" type="date" value="2026-09-20"></div>
        </div>
        <div class="field">
          <label for="end">Volta / check-out</label>
          <div class="input-wrap"><span class="ico">▣</span><input id="end" type="date" value="2026-09-21"></div>
        </div>
        <div class="search-action">
          <button id="go" disabled>⌕ &nbsp; Pesquisar ao vivo &nbsp; →</button>
          <button id="tripLink" type="button" aria-live="polite">🔗 Link da viagem</button>
        </div>
      </div>

      <div class="search-status">
        <div class="status-icon" id="statusIcon">✓</div>
        <div>
          <div id="status">Inicializando workers persistentes…</div>
          <div class="progress"><div id="bar" class="bar"></div></div>
        </div>
        <div class="status-note">Resultados entram conforme ficam prontos.</div>
      </div>
    </section>

    <section class="cards">
      <article class="card flight" id="flightCard">
        <div class="card-head">
          <div class="card-label"><div class="card-icon">✈</div><div><h3>Passagem</h3><div class="card-sub">Voos encontrados</div></div></div>
          <div class="time" id="flightTime">—</div>
        </div>
        <div class="card-body" id="flightBody">
          <div class="metric-label">Menor preço</div><div class="metric-value">—</div>
          <div class="detail-box">Aguardando pesquisa</div>
        </div>
        <button type="button" class="see-all" data-module="flight" aria-haspopup="dialog" aria-controls="detailsModal" aria-label="Ver todos os voos" disabled>Ver todos →</button>
      </article>

      <article class="card hotel" id="hotelCard">
        <div class="card-head">
          <div class="card-label"><div class="card-icon">🛏</div><div><h3>Hospedagem</h3><div class="card-sub">Hotéis encontrados</div></div></div>
          <div class="time" id="hotelTime">—</div>
        </div>
        <div class="card-body" id="hotelBody">
          <div class="metric-label">Melhor opção</div><div class="metric-value">—</div>
          <div class="detail-box">Aguardando pesquisa</div>
        </div>
        <button type="button" class="see-all" data-module="hotel" aria-haspopup="dialog" aria-controls="detailsModal" aria-label="Ver todos os hotéis" disabled>Ver todos →</button>
      </article>

      <article class="card car" id="carCard">
        <div class="card-head">
          <div class="card-label"><div class="card-icon">🚗</div><div><h3>Carro</h3><div class="card-sub">Ofertas encontradas</div></div></div>
          <div class="time" id="carTime">—</div>
        </div>
        <div class="card-body" id="carBody">
          <div class="metric-label">Melhor opção</div><div class="metric-value">—</div>
          <div class="detail-box">Aguardando pesquisa</div>
        </div>
        <button type="button" class="see-all" data-module="car" aria-haspopup="dialog" aria-controls="detailsModal" aria-label="Ver todos os carros" disabled>Ver todos →</button>
      </article>

      <article class="card event" id="eventCard">
        <div class="card-head">
          <div class="card-label"><div class="card-icon">🎟</div><div><h3>Evento</h3><div class="card-sub">Eventos encontrados</div></div></div>
          <div class="time" id="eventTime">—</div>
        </div>
        <div class="card-body" id="eventBody">
          <div class="metric-label">Agenda no período</div><div class="metric-value">—</div>
          <div class="detail-box">Aguardando pesquisa</div>
        </div>
        <button type="button" class="see-all" data-module="event" aria-haspopup="dialog" aria-controls="detailsModal" aria-label="Ver todos os eventos" disabled>Ver todos →</button>
      </article>
    </section>

    <section class="calc">
      <div class="calc-title">
        <div class="calc-icon">▦</div>
        <div><h2>Calculadora da viagem</h2><p>Soma dos menores preços confirmados.</p></div>
      </div>
      <div class="breakdown" id="breakdown">
        <span class="cost-chip">✈ Voo: —</span>
        <span class="cost-chip">🛏 Hotel: —</span>
        <span class="cost-chip">🚗 Carro: —</span>
        <span class="cost-chip">🎟 Evento: —</span>
      </div>
      <div class="total-wrap"><div class="total-label">MENOR TOTAL CONFIRMADO</div><div id="total" class="total">R$ —</div></div>
    </section>
  </main>
</div>

<nav class="mobile-nav" aria-label="Navegação móvel">
  <button class="active" type="button">⌂<br>Início</button>
  <button type="button" disabled title="Em breve">♡<br>Salvos</button>
  <button type="button" disabled title="Em breve">⚙<br>Ajustes</button>
</nav>

<dialog id="detailsModal" class="details-modal" aria-labelledby="detailsTitle" aria-describedby="detailsNote">
  <div class="details-head">
    <h2 id="detailsTitle">Detalhes</h2>
    <button type="button" class="details-close" id="detailsClose" aria-label="Fechar detalhes" autofocus>×</button>
  </div>
  <p id="detailsNote" class="details-note"></p>
  <ul id="detailsList" class="details-list"></ul>
</dialog>

<script>
const $=id=>document.getElementById(id);
let ready=false, prices={flight:null,hotel:null,car:null,event:null};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const brl=v=>v==null?'—':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(v);
const tripFields=['fo','fd','hc','cl','ec','start','end'];
let autoRunPending=false, searchRunning=false, linkFeedbackTimer;
function restoreTripLink(){
  const params=new Map();
  let malformed=false;
  for(const part of location.search.slice(1).split('&')){
    if(!part)continue;
    const separator=part.indexOf('=');
    const key=separator<0?part:part.slice(0,separator);
    const value=separator<0?'':part.slice(separator+1);
    try{
      params.set(decodeURIComponent(key.replace(/\+/g,' ')),decodeURIComponent(value.replace(/\+/g,' ')));
    }catch{malformed=true}
  }
  for(const id of tripFields){
    if(params.has(id))$(id).value=params.get(id);
  }
  const complete=tripFields.every(id=>params.has(id)&&$(id).value.trim());
  const validDates=['start','end'].every(id=>{
    const value=$(id).value;
    const date=new Date(value+'T00:00:00Z');
    return /^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;
  });
  autoRunPending=!malformed&&params.get('run')==='1'&&complete&&validDates&&$('end').value>$('start').value;
}
function maybeRunTrip(){
  if(!autoRunPending||!ready||searchRunning||$('go').disabled)return;
  autoRunPending=false;
  $('go').click();
}
function copyTripFallback(text){
  const field=document.createElement('textarea');
  const focused=document.activeElement;
  field.value=text;
  field.readOnly=true;
  field.style.cssText='position:fixed;top:0;left:-9999px;font-size:16px';
  document.body.appendChild(field);
  try{
    field.focus({preventScroll:true});
    field.select();
    field.setSelectionRange(0,field.value.length);
    return document.execCommand('copy');
  }finally{
    field.remove();
    if(focused instanceof HTMLElement)focused.focus({preventScroll:true});
  }
}
$('tripLink').addEventListener('click',async()=>{
  const button=$('tripLink');
  if(button.disabled)return;
  clearTimeout(linkFeedbackTimer);
  button.disabled=true;
  button.textContent='Copiando…';
  try{
    const query=tripFields.map(id=>`${encodeURIComponent(id)}=${encodeURIComponent($(id).value)}`).join('&');
    const url=`${location.origin}${location.pathname}?${query}&run=1`;
    let copied=false;
    if(navigator.clipboard&&window.isSecureContext){
      try{await navigator.clipboard.writeText(url);copied=true}catch{}
    }
    if(!copied)copied=copyTripFallback(url);
    if(!copied)throw new Error('Clipboard indisponível');
    button.textContent='Link copiado ✓';
  }catch{
    button.textContent='Cópia bloqueada. Tente novamente.';
  }finally{
    button.disabled=false;
    linkFeedbackTimer=setTimeout(()=>{button.textContent='🔗 Link da viagem'},4000);
  }
});

let detailPayloads=Object.create(null), detailQuery={};
const detailTitles={flight:'Voos',hotel:'Hospedagens',car:'Carros',event:'Eventos'};
const detailSites={hotel:'https://www.booking.com/',car:'https://www.discovercars.com/',event:'https://shotgun.live/'};
function detailMoney(value,currency){
  if(value==null||String(value).trim()==='')return 'Preço não informado';
  const amount=Number(value);
  if(!Number.isFinite(amount)||amount<0)return 'Preço não informado';
  const code=String(currency||'BRL').toUpperCase();
  try{return new Intl.NumberFormat('pt-BR',{style:'currency',currency:code}).format(amount)}
  catch{return `${amount.toLocaleString('pt-BR')} ${code}`}
}
function detailUrl(value){
  if(typeof value!=='string'||!value.trim())return '';
  try{
    const url=new URL(value);
    return ['https:','http:'].includes(url.protocol)?url.href:'';
  }catch{return ''}
}
function detailRows(k,r){
  if(k==='flight'){
    const rows=Array.isArray(r.top_prices)?r.top_prices:[];
    return rows.map((value,i)=>{
      const row=value&&typeof value==='object'?value:{price:value};
      return {...row,name:row.name||`Opção de voo ${i+1}`};
    });
  }
  return Array.isArray(r.results)?r.results:[];
}
function openDetails(k){
  const r=detailPayloads[k];
  if(!r||!r.ok)return;
  const rows=detailRows(k,r);
  const flightQuery=`Voos de ${detailQuery.origin||''} para ${detailQuery.dest||''} em ${detailQuery.start||''}`;
  const fallback=k==='flight'?`https://www.google.com/travel/flights?hl=pt-BR&curr=BRL&q=${encodeURIComponent(flightQuery)}`:detailSites[k];
  $('detailsTitle').textContent=`${detailTitles[k]} · ${rows.length} opção(ões)`;
  $('detailsNote').textContent=(k==='flight'?'Até 5 preços retornados pelo motor. ':k==='hotel'||k==='car'?'Até 30 opções retornadas pelo motor. ':'')+'Apenas resultados desta busca, sem nova consulta. O site externo pode atualizar preços.';
  $('detailsList').innerHTML=rows.length?rows.map((value,i)=>{
    const row=value&&typeof value==='object'?value:{};
    const name=row.name||row.title||`${detailTitles[k]} ${i+1}`;
    let meta=[];
    if(k==='flight')meta=[detailQuery.origin,detailQuery.dest,detailQuery.start];
    if(k==='hotel')meta=[row.stars!=null?`${row.stars} estrela(s)`:'',row.total!=null?'Total da estadia':'Preço coletado'];
    if(k==='car')meta=[row.supplier,'Total da locação'];
    if(k==='event')meta=[row.date||row.datetime||row.startDate||row.start,row.venue||row.place||row.location];
    const price=detailMoney(k==='hotel'?(row.total??row.price):row.price,row.currency);
    const direct=detailUrl(row.url)||detailUrl(row.link)||detailUrl(row.event_url);
    const href=direct||fallback;
    const label=direct?'Abrir oferta':k==='flight'?'Consultar no Google Flights':'Abrir site do fornecedor';
    return `<li><h3>${esc(name)}</h3><p class="details-meta">${meta.filter(v=>v!=null&&v!=='').map(esc).join(' · ')}</p><p class="details-price">${esc(price)}</p><a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${label} ↗<span class="details-meta"> (nova aba)</span></a></li>`;
  }).join(''):'<li>Nenhum resultado disponível para esta busca.</li>';
  if(!$('detailsModal').open)$('detailsModal').showModal();
}
$('detailsClose').addEventListener('click',()=>$('detailsModal').close());
$('detailsModal').addEventListener('cancel',e=>{
  e.preventDefault();
  $('detailsModal').close();
});
$('detailsModal').addEventListener('click',e=>{
  if(e.target!==e.currentTarget)return;
  const rect=e.currentTarget.getBoundingClientRect();
  if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)e.currentTarget.close();
});
document.addEventListener('click',e=>{
  const button=e.target instanceof Element?e.target.closest('.see-all'):null;
  if(button&&!button.disabled)openDetails(button.dataset.module);
});

function setLoading(k){
  $(k+'Time').textContent='…';
  $(k+'Card').classList.add('loading');
  $(k+'Body').innerHTML='<div class="skeleton" style="width:52%"></div><div class="skeleton" style="width:78%"></div><div class="skeleton" style="width:64%"></div>';
}
function reset(){
  if($('detailsModal').open)$('detailsModal').close();
  $('detailsList').replaceChildren();
  detailPayloads=Object.create(null);
  detailQuery={origin:$('fo').value.trim(),dest:$('fd').value.trim(),start:$('start').value};
  document.querySelectorAll('.see-all').forEach(button=>{button.disabled=true});
  prices={flight:null,hotel:null,car:null,event:null};
  ['flight','hotel','car','event'].forEach(setLoading);
  $('total').textContent='R$ —';
  $('breakdown').innerHTML='<span class="cost-chip">✈ Voo: —</span><span class="cost-chip">🛏 Hotel: —</span><span class="cost-chip">🚗 Carro: —</span><span class="cost-chip">🎟 Evento: —</span>';
  $('bar').style.width='8%';
}
function calc(){
  const items=[['✈ Voo','flight'],['🛏 Hotel','hotel'],['🚗 Carro','car'],['🎟 Evento','event']];
  const confirmed=items.map(([label,key])=>[label,prices[key]]).filter(([,v])=>typeof v==='number'&&v>0);
  const sum=confirmed.reduce((a,[,v])=>a+v,0);
  $('total').textContent=confirmed.length?brl(sum):'R$ —';
  $('breakdown').innerHTML=items.map(([label,key])=>`<span class="cost-chip">${label}: ${prices[key]==null?'não incluído':brl(prices[key])}</span>`).join('');
}
function failCard(k,r){
  $(k+'Card').classList.remove('loading');
  $(k+'Body').innerHTML=`<div class="metric-label">Não foi possível concluir</div><div class="detail-box"><b>Falhou</b><br>${esc(r.error||'Erro desconhecido')}</div>`;
}
function renderModule(r){
  const map={flights:'flight',hotels:'hotel',cars:'car',events:'event'}, k=map[r.module]; if(!k)return;
  $(k+'Card').classList.remove('loading');
  $(k+'Time').textContent=(r.seconds??0).toFixed(2)+'s';
  const detailButton=document.querySelector(`.see-all[data-module="${k}"]`);
  delete detailPayloads[k];
  detailButton.disabled=true;
  if(!r.ok){failCard(k,r);return}
  detailPayloads[k]=r;
  detailButton.disabled=false;
  if(k==='flight'){
    prices.flight=Number(r.price)||null;
    $(k+'Body').innerHTML=`<div class="metric-label">Menor preço</div><div class="metric-value">${brl(prices.flight)}</div><div class="detail-box"><b>${r.price_count||0}</b> preços analisados</div>`;
  } else if(k==='hotel'){
    const first=(r.top||[])[0];
    prices.hotel=Number(r.best_price)||null;
    $(k+'Body').innerHTML=`<div class="metric-label">${r.count||0} hospedagens · melhor opção</div><div class="metric-value">${brl(prices.hotel)}</div><div class="detail-box">${first?`<b>${esc(first.name||'Hospedagem')}</b>`:'Sem preço confirmado'}</div>`;
  } else if(k==='car'){
    const first=(r.top||[])[0];
    prices.car=Number(r.best_price)||null;
    $(k+'Body').innerHTML=`<div class="metric-label">${r.count||0} ofertas · melhor opção</div><div class="metric-value">${brl(prices.car)}</div><div class="detail-box">${first?`<b>${esc(first.name||'Carro')}</b>${first.supplier?` · ${esc(first.supplier)}`:''}`:'Sem preço confirmado'}</div>`;
  } else {
    const rows=(r.results||[]);
    const priced=rows.map(x=>Number(x.price)).filter(v=>Number.isFinite(v)&&v>0);
    prices.event=priced.length?Math.min(...priced):null;
    const list=rows.length?rows.map((x,i)=>{
      const name=esc(x.name||x.title||`Evento ${i+1}`);
      const when=esc(x.date||x.datetime||x.startDate||x.start||'');
      const venue=esc(x.venue||x.place||x.location||'');
      const price=Number(x.price)>0?brl(Number(x.price)):'';
      const meta=[when,venue,price].filter(Boolean).join(' · ');
      return `<div class="event-item"><div class="event-name">${name}</div>${meta?`<div class="event-meta">${meta}</div>`:''}</div>`;
    }).join(''):`<div class="event-item">Nenhum evento confirmado${r.pages_scanned?` · ${r.pages_scanned} pág. verificadas`:''}</div>`;
    $(k+'Body').innerHTML=`<div class="metric-label">Agenda no período</div><div class="metric-value">${r.count||rows.length||0} evento(s)</div><div class="event-list">${list}</div>`;
  }
  calc();
}
async function pollReady(){
  try{
    const r=await fetch('/api/status'); const j=await r.json();
    ready=j.ready;
    $('go').disabled=!ready||searchRunning;
    if(searchRunning)return;
    if(ready&&j.warm_failures&&j.warm_failures.length){
      $('readyBadge').innerHTML='<span style="color:#ffcc00">●</span><span><b>Motores prontos, warmup parcial</b><small>'+j.warm_failures.join('; ')+'</small></span>';
      $('status').textContent='Pronto — busca seguirá mesmo com warmup pendente.';
    }else if(ready){
      $('readyBadge').innerHTML='<span class="engine-dot"></span><span><b>Motores quentes</b><small>Todos os módulos prontos</small></span>';
      $('status').textContent='Pronto para pesquisar ao vivo.';
      $('bar').style.width='100%';
    }else if(j.error){
      $('readyBadge').innerHTML='<span style="color:#ff8b8b">●</span><span><b>Falha no boot</b><small>Verifique o terminal</small></span>';
      $('status').textContent=j.error;
    }else{
      $('status').textContent=j.stage||'Inicializando…';
    }
  }catch(e){$('status').textContent='Servidor iniciando…'}
  maybeRunTrip();
  if(!ready)setTimeout(pollReady,1000)
}

// v3.8.2 — Re-sincroniza o frontend após cache,
// hard refresh e retorno de aba.
window.addEventListener('pageshow', pollReady);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) pollReady();
});

$('go').addEventListener('click',async()=>{
  if(!ready||searchRunning)return;
  autoRunPending=false;
  searchRunning=true;
  reset(); $('go').disabled=true; $('status').textContent='Pesquisa ao vivo iniciada…';
  const payload={flight_origin:$('fo').value.trim(),flight_dest:$('fd').value.trim(),hotel_city:$('hc').value.trim(),car_location:$('cl').value.trim(),event_city:$('ec').value.trim(),start:$('start').value,end:$('end').value,limit:5};
  try{
    const resp=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!resp.ok)throw new Error(`HTTP ${resp.status}`);
    const reader=resp.body.getReader(),dec=new TextDecoder();let buf='',doneCount=0;
    while(true){
      const {value,done}=await reader.read(); if(done)break;
      buf+=dec.decode(value,{stream:true}); const lines=buf.split('\n'); buf=lines.pop();
      for(const line of lines){
        if(!line.trim())continue; const ev=JSON.parse(line);
        if(ev.type==='module'){renderModule(ev.data);doneCount++;$('bar').style.width=(20+doneCount*20)+'%';}
        if(ev.type==='done'){$('status').textContent=`Busca concluída em ${ev.wall.toFixed(2)}s`; $('bar').style.width='100%';calc();}
        if(ev.type==='status')$('status').textContent=ev.message;
        if(ev.type==='error')$('status').textContent=ev.error||'Erro na busca';
      }
    }
  }catch(err){
    $('status').textContent=`Erro: ${err.message}`;
  }finally{
    searchRunning=false;
    $('go').disabled=!ready;
  }
});
restoreTripLink();
pollReady();
</script>
</body>
</html>'''

class EngineState:
    def __init__(self):
        self.workers = {}
        self.ready = False
        self.stage = "Inicializando workers persistentes…"
        self.error = None
        self.lock = threading.Lock()
        threading.Thread(target=self._boot, daemon=True).start()

    def _boot(self):
        self.warm_failures = []
        try:
            for name in ("flights", "cars", "hotels"):
                self.stage = f"Subindo {name}…"
                self.workers[name] = ProcessWorker(name)
                self.workers[name].wait("READY", timeout=120)

            self.stage = "Aquecendo Flights…"
            self.workers["flights"].send({"op":"warm","origin":DEFAULTS["flight_origin"],
                                          "dest":DEFAULTS["flight_dest"],"start":DEFAULTS["start"]})
            try:
                self.workers["flights"].wait("WARM", timeout=120)
            except Exception as exc:
                self.warm_failures.append(f"flights: {type(exc).__name__}")

            self.stage = "Aquecendo Cars…"
            self.workers["cars"].send({"op":"warm"})
            try:
                self.workers["cars"].wait("WARM", timeout=120)
            except Exception as exc:
                self.warm_failures.append(f"cars: {type(exc).__name__}")

            self.stage = "Aquecendo Booking…"
            self.workers["hotels"].send({"op":"warm","city":DEFAULTS["hotel_city"],
                                         "start":DEFAULTS["start"],"end":DEFAULTS["end"]})
            try:
                self.workers["hotels"].wait("WARM", timeout=120)
            except Exception as exc:
                self.warm_failures.append(f"hotels: {type(exc).__name__}")

            # v3.8.7 — warmup falho NÃO pode bloquear a busca. Os searches têm
            # retry próprio; warmup é só vantagem de latência.
            self.stage = "Assentando sessões…"
            time.sleep(3.0)
            self.ready = True
            if self.warm_failures:
                self.stage = (
                    "Pronto (warmup parcial: "
                    + "; ".join(self.warm_failures) + ")"
                )
            else:
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

            # v3.8.8 — Events espera 20s p/ não disputar CPU/rede com o Flight.
            def _events_later(event_city, start, end, limit):
                time.sleep(20)
                return run_events(event_city, start, end, limit)
            ef = executor.submit(_events_later, p["event_city"], p["start"], p["end"], int(p.get("limit",5)))

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
            self._send_json({"ready":STATE.ready,"stage":STATE.stage,
                             "error":STATE.error,
                             "warm_failures":getattr(STATE, "warm_failures", [])})
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
