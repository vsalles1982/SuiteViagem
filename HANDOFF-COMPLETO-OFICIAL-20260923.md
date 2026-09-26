# HANDOFF COMPLETO — Suíte de Viagens (OFICIAL)

> **Agente responsável:** OPENCODE (agente oficial)
> **Data:** 2026-09-23 — **Status da fase:** ✅ CONSISTÊNCIA 4×4 CONCLUÍDA
> **Destinatário:** agente reserva (retomada)
> **Repositório oficial (git):** `/home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem`
> **Commit HEAD:** `1258484` — **Tag do campeão:** `campeao-4x4-v3_8_8`
> **Pacote entregue:** `~/Downloads/suiteviagem-web-v3_8_8-campeao-4x4-20260923.zip`

---

## 1. RESUMO EXECUTIVO

A Suíte de Viagens consulta **4 motores em paralelo** e os mostra ao vivo na web:
✈ Google Flights (voo) · 🛏 Booking (hospedagem) · 🚗 DiscoverCars (carro) · 🎟 Shotgun (evento).

**Missão da fase:** fazer os **4 cards ficarem verdes em uma única busca**, de forma
repetível. Causa-raiz: **não era 1 bug, eram 6 bugs empilhados** que se mascaravam.
**Estado final:** os 4 módulos passam juntos (`ok=true`) com o **agenda de eventos
escalonada**, voo com retry robusto e bridges de drivers (Cars/Hotel) isolados.

> ⚠️ **Importante para o reserva:** o servidor web está **DESLIGADO** neste momento
> (porta 8787 livre; ver seção 6 para religar).

---

## 2. EVIDÊNCIA DO CAMPEÃO (última corrida registrada, `--start 2026-11-07`)

Arquivo: `resultados_paralelo/parallel_arena_v3_20260923-065108-725959.json`

| Módulo | ok | Tempo de busca | Melhor preço | Detalhe |
|---|---|---|---|---|
| ✈ Voos | ✅ `true` | 20,678 s | R$ 390,00 | 144 preços, `session_reused` |
| 🚗 Carro | ✅ `true` | 43,712 s | R$ 161,97 (Fiat Mobi · Foco) | 5 ofertas |
| 🛏 Hotel | ✅ `true` | 74,707 s | R$ 190,00 (Hospedaria N. S. da Glória) | 15 ofertas |
| 🎟 Evento | ✅ `true` | 98,436 s | — (0 na janela) | 15 páginas / 218 links varridos |

`heavy_gate_reason: "gate_timeout_9s"` · `user_query_wall_seconds: 107.455`

> Observação do evento: `ok=true` mesmo com **0 resultados na janela** (07–08/11 em
> São Paulo não tinha eventos; o card verde com "0 evento(s)" é o comportamento correto).
> ✅ Prova anterior (12/09) já havia registrado corridas com eventos positivos no intervalo.

---

## 3. LINHA DO TEMPO — TUDO QUE FOI FEITO (git log oficial)

| Commit | Data | Entregue |
|---|---|---|
| `ff66392` | 06–09 03:11 | Contrato comum + histórico SQLite da SuiteViagem |
| `7bfdcbe` | 06–09 03:25 | Integra Shotgun ao histórico (preços e cobertura) |
| `878f12b` | 06–09 03:41 | Integra DiscoverCars ao histórico comum |
| `35f2185` | 06–09 18:24 | Integra Booking ao histórico com preços e taxas |
| `ab18cd6` | 06–09 20:14 | Integra Google Flights ao histórico preservando RSS |
| `48dfd4d` | 07–09 20:58 | Realm: interface web + hotéis progressivos + carros com retirada validada |
| `34ec866` | 09–09 21:54 | Medição de etapas dos carros + leitura agrupada das sugestões |
| `a1e9363` | 10–09 07:50 | DiscoverCars fast-path v17 (create-search direto) |
| `9f135b8` | 11–09 01:01 | v18 warm-driver checkpoint (Chromium persistente, 16/16 testes) |
| `57a5add` | 11–09 03:10 | v19 worker web persistente (tag `cars-web-warm-v19`) |
| `d353d80` | 23–09 06:45 | Restauração arena v3.8.6 + retry do Google Flights |
| `1258484` | 23–09 07:28 | **v3.8.8 definitiva:** retry ~100 s + events adiado + warmup não-bloqueante |

Tag `campeao-4x4-v3_8_8` → aponta para o HEAD atual. **Árvore de trabalho limpa** (`git status` vazio).

---

## 4. OS 6 BUGS EMPILHADOS QUE FORAM CORRIGIDOS (a "consistência")

O sintoma mudava a cada execução porque 6 causas se sobrepunham:

1. **Lock do perfil Chrome compartilhado** entre Cars e Hotel → `NoSuchWindow` / `InvalidSessionId` em idle.
2. **`/tmp` enchendo de `scoped_dir_*`** (vários Chromium no mesmo `TMPDIR`) → crashes silenciosos.
3. **Playwright sync iniciado em thread com asyncio loop ativo** (thread do servidor web) → Voos falhava silenciosamente.
4. **DiscoverCars derrubava a janela do Chrome durante o prewarm** → driver morto no `search` → card vermelho.
5. **Erros engolidos sem emitir `DONE:`** → orquestração esperava resposta que nunca chegava.
6. **Estado acumulado fora do código** (`/tmp`, `~/.cache`) sobrevivendo entre execuções.

> Sintoma típico com que o reserva vai esbarrar de novo: "3 verdes + 1 vermelho",
> alternando QUAL fica vermelho a cada execução. Isso é o sintoma clássico de
> **contenção de recursos** (disco/perfil/loop) — NÃO é bug de seletor de DOM.

### 4.1 Correções por arquivo (caminhos relativos ao repo oficial)

**✈ `passagens/google-flights/google_flights_fastpath.py`**
- `:50` (v3.8.5) `_safe_sync_playwright_start()` — sobe Playwright em thread limpa quando há asyncio loop.
- `:14` (v3.8.8) regex genérica de fallback `[[null,<preço>]` (o Google varia o token após o preço).
- `:136` (v3.8.8) retry com `waits = (20, 25, 25, 30)` + `page.reload()` quando o RPC atrasa sob carga.
- `:107` (v3.8.8) diagnóstico `rpc_seen` / `no_price_bodies` (falha nunca sai sem evidência).

**🚗 `module_worker_v3.py` (orquestrador de workers)**
- `:135–172` (v3.8.5) `_driver_alive()`/`_is_dead_driver()`/`_rebuild()`: checa driver vivo pós-warmup, recria antes do search, e **retenta** se o driver cair no meio do search. **`DONE:` é sempre emitido.**

**🚗 `suiteviagem/cars_worker_v20e.py`**
- `:53–60` (v3.8.5) perfil Chrome **novo a cada sessão** via `tempfile.mkdtemp` (único até em rebuild onde PID não muda) — elimina lock do perfil.
- Evolução do motor: `v20d` (endpoint `/api/v2/search/<uuid>`) → **v20E** parse estruturado + validação + fallback DOM → **v20F** transport via `fetch()` no browser quente → **v20G** consulta direta ao endpoint sem abrir `/search/`.

**🛏 `booking-hotel-scraper/hotels_booking.py`**
- `:61–66` (v3.8.3) perfil Chrome isolado por processo (`chrome_hotel_<pid>`).
- `:81–84` (v3.8.3) flags anti-idle (desativa throttling de timer/background do Chromium).
- `:250` fast-path SSR (lote inicial, sem scroll) + `:492` `query_matches` confirma URL/parâmetros a cada leitura.

**🎟+🧠 `parallel_arena_v3.py` (orquestração)**
- `:42–48` (v3.8.4) `TMPDIR` isolado por worker (`~/.cache/suiteviagem/tmp_<modulo>`) — resolve o bug do `/tmp`.
- `:382–384` (v3.8.8) `_events_later` adia Events em **20 s** → não compete com a janela crítica do RPC de Voos.
- Escalonamento: warmup sequencial → settle 3 s → FASE A (Voos sozinho) → gate 9 s → FASE B (Cars, Booking 0,20 s depois, Events).

**🌐 `suiteviagem_web.py`**
- `:450–452` (v3.8.2) re-sync do frontend após cache/hard refresh/retorno de aba (`pageshow` + `visibilitychange`).

---

## 5. ARQUITETURA ATUAL (como as peças funcionam juntas)

```
suiteviagem_web.py  (ThreadingHTTPServer :8787, página + /api/status + /api/search NDJSON)
        │  sobe 3 subprocessos persistentes (module_worker_v3.py)
        ▼
 ProcessWorker (protocolo de linha JSON: READY: / WARM: / DONE: / CAR_LOG: ; comando {"op": ...})
   ├─ flights → google_flights_fastpath.py (Playwright, RPC GetShoppingResults)
   ├─ cars    → suiteviagem/cars_worker_v20g.py (Selenium + direct API v20G)
   └─ hotels  → hotels_booking.py (Selenium + fast-path SSR)
 Eventos → run_events() na thread do próprio servidor (Shotgun, requests + BeautifulSoup)
```

- FASE A: **Flights sozinho** em atividade; Cars/Booking ociosos.
- Gate de 9 s: se Flights não terminar, FASE B é liberada por timeout.
- FASE B: Events (delay 20 s) → Cars → Booking (+0,20 s).
- Cada worker vive num processo isolado com **perfil Chrome e TMPDIR próprios**.

---

## 6. COMO LIGAR / DESLIGAR / DEPURAR

```bash
# LIGAR (a partir do repositório oficial — é quem roda de verdade hoje)
cd /home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem
./.venv/bin/python suiteviagem_web.py
# abrir http://127.0.0.1:8787   →   esperar "Motores quentes"  →   Pesquisar ao vivo

# DESLIGAR (ou Ctrl+C no terminal onde está rodando)
pkill -f suiteviagem_web.py

# Rodar a arena em modo terminal (equivalente CLI da busca completa)
./.venv/bin/python parallel_arena_v3.py \
  --flight-origin RIO --flight-dest SAO --hotel-city "Petrópolis" \
  --car-location "Sao Paulo Guarulhos Airport (GRU), Sao Paulo, Brazil" \
  --event-city "São Paulo" --start 2026-09-20 --end 2026-09-21 --limit 5
```

- Logs dos workers aparecem no stdout do servidor com prefixos `[flights] [cars] [hotels]`.
- Toda corrida grava `resultados_paralelo/parallel_arena_v3_<timestamp>.json`.
- Consulta campeã embutida: RIO→SAO · Petrópolis · GRU · São Paulo · 20/09→21/09.
- Booking segue **headful** (modo confiável validado).

---

## 7. DOIS MUNDOS DE CÓDIGO — A TENDA DAS VERSIONS

Existem **duas cópias** do projeto. O reserva PRECISA saber qual é oficial:

| Cópia | Status | Papel |
|---|---|---|
| **`/home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem`** | ⭐ **OFICIAL** (git, HEAD `1258484`, tag `campeao-4x4-v3_8_8`) | é a que **roda** (instância atual) |
| **`/home/vsalles/Work/suite-viagens`** | cópia **parcial/defasada** (sem `.git`, sem `scraper_carro/`, sem `tests/`, etc.) | documentação/handoffs; pode ser sincronizada do oficial |

⚠️ **Regra:** qualquer alteração real vai no **repo oficial (git)**. A cópia de
`Work/suite-viagens` está **atrás** da v3.8.8 (não tem o retry de Flights nem o
delay de Events) — não usá-la como base de código. O print salvo pelo usuário e o
handoff de consistência (`Work/suite-viagens/HANDOFF-CONSISTENCIA-4X4-20260923.md`)
são documentos, não código.

---

## 8. REGRAS DE OURO (não quebrar a consistência)

1. **Sempre emitir `READY:`/`WARM:`/`DONE:`** com `ok` explícito; erro nunca engolido.
2. **Perfil Chrome isolado por processo/sessão** (Cars e Hotel) — `mkdtemp` no rebuild.
3. **`TMPDIR` sempre por worker** — nunca `/tmp` global para vários Chromium.
4. **Playwright sync** → usar `_safe_sync_playwright_start()` (nunca no thread com asyncio loop ativo).
5. **Manter fallback em camadas:** Flights (rounds 20/25/25/30) · Cars (v20G→v20E→DOM v20C) · Hotels (fast SSR→legado).
6. **Manter escalonamento da FASE B** — Flights fica sozinho na janela crítica; Events atrasados.
7. Seabagem visual = `visual-only pass` ao estilo v3.8; **qualquer regressão de coleta revoga para `suiteviagem/web/champion_v372/`**.
8. Varrer `~/.cache/suiteviagem/` e `/tmp` entre sessões de teste para evitar acúmulo de `scoped_dir_*`.

---

## 9. DEPENDÊNCIAS (`.venv` do repo oficial, Python 3.14)

`beautifulsoup4`, `geopy`, `openpyxl`, `pandas`, `playwright` (1.62, chromium headless
instalado), `requests`, `rich`, `selenium`, `selenium-stealth`, `textual`,
`timezonefinder`, `webdriver-manager`. Chromium do sistema: `/usr/bin/chromium`.

---

## 10. PRÓXIMAS ETAPAS (alinhar com o agente reserva) — sugeridas pelo oficial

Prioridade sugerida (P0 = operacional, P1 = robustez, P2 = roadmap do produto):

### P0 — Consolidação e latência (crítico antes de feature nova)
- **Sincronizar as duas cópias de código.** Fazer de `Work/suite-viagens` um clone/
  espelho do repo oficial (ou apontar o usuário para usar só o oficial). Evitar o
  "two worlds" voltando.
- **Reduzir o wall time (107 s).** Gargalos medidos no último run:
  - Hotel: `driver_seconds 16,8 s` (driver frio) e `navigation_seconds 44,5 s`.
    Investigar warmup do Booking headful e reuso do driver (`driver_reused=false`).
  - Events: `sleep(20)` fixo — tornar adaptativo (só atrasar se Flights ainda ativo)
    e limitar paginação para janelas curtas.
- **Validar o card de Eventos com resultados reais** numa janela que tenha eventos
  (ex.: São Paulo em fim de semana próximo) — o último run teve 0 eventos na janela.

### P1 — Robustez
- Reativar suíte `pytest` antes de qualquer mudança (16/16 dos carros na v18);
  adicionar testes unitários para os helpers novos de Flights (v3.8.5/8).
- Cancelamento de busca: `interface-web-v1.md` registra pendência — consulta pode
  ficar `running` no histórico; recuperação/checkpoint incremental pendentes.
- Conferência independente de parâmetros (docs marcam `effective.confirmed_parameters`
  como nulos em alguns módulos) — fechar esse gap de auditoria.
- Botão/status de engine no front realizar 100% do ciclo (ids de busca por sessão).

### P2 — Roadmap original do README (não iniciado)
- Feeds RSS por módulo + agregação no **Newsboat** (objetivo raiz do projeto).
- **Timers do systemd** para consultas automáticas recorrentes.
- **Histórico de preços** com detecção de quedas e novos eventos.
- Padronizar saída/exportação dos 4 módulos num formato comum (contrato SQLite já existe).

### P2 — Gestão de envelope de entrega
- Varrer `~/.cache/suiteviagem/` e `/tmp` pós-teste.
- Re-empaquetar zip final se houver novos commits (ex.: v3.8.9).
- Considerar `git tag` + release notes por pacote entregue.

---

## 11. ARTEFATOS E REFERÊNCIAS

- Pacote campeão: `~/Downloads/suiteviagem-web-v3_8_8-campeao-4x4-20260923.zip`
- Versão anterior (base de comparação): `~/Downloads/suiteviagem-web-v3_8_1-photo-backgrounds/`
- Print do usuário (salvo): pasta `~/Downloads/FireShot/` (capturas da página ao vivo)
- Handoff de consistência (detalhado por bug): `~/Work/suite-viagens/HANDOFF-CONSISTENCIA-4X4-20260923.md`
- Handoffs intermediários (estado quebrado): `~/Downloads/handoff.md`, `suiteviagem2.md`, `suiteviagem3.txt`
- Docs técnicos de evolução: `docs/` (repo oficial: `*-v*.md`, `checkpoints/`)

---

## 12. MENSAGEM CURTA PARA O AGENTE RESERVA

> Repositório oficial: `/home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem`
> (git, tag `campeao-4x4-v3_8_8`). 4/4 módulos passam. Consistência veio de:
> perfis/TMPDIR Chrome isolados, Playwright fora de thread com asyncio,
> driver de Cars com rebuild+retry, retry do RPC de Voos, Events adiado.
> NÃO edite `Work/suite-viagens` (cópia defasada). Servidor está desligado;
> ligue com `./.venv/bin/python suiteviagem_web.py`. Próxima prioridade: latência
> total (107 s → objetivo <60 s): Hotel navigation 44,5 s e delay fixo de 20 s em Events.