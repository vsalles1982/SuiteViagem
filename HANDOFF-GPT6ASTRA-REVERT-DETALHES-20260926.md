# HANDOFF — Experimento "Ver todos (detalhes do card)" — REVERTIDO

> Este documento é OBRIGATÓRIO para quem assumir a Suíte de Viagens a partir de agora (GPT-6 Astra).
> Leia até o fim antes de tocar em QUALQUER arquivo. As decisões abaixo estão endossadas pelo dono do projeto.

---

## 1. ESTADO ATUAL — PONTO DE PARTIDA (NÃO MEXER NESSA BASE)

- **Repo oficial (foi este que voltamos a usar)**: `/home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem`
  - HEAD: `1258484` — "estabilidade flight v3.8.8"
  - Tag: **`campeao-4x4-v3_8_8`** ✅
  - Árvore git **LIMPA** (git status só mostra 1 doc não-rastreado: `HANDOFF-COMPLETO-OFICIAL-20260923.md`)
- **Servidor web**: rodando e pronto em `http://127.0.0.1:8787`
  - subir: `setsid /tmp/opencode/start_web.sh </dev/null >/dev/null 2>&1 &`
  - parar: usar `/tmp/opencode/scan_kill.py` (NUNCA `pkill -f suiteviagem_web.py` — casa com a própria linha de comando e se auto-mata)
- **Backups da versão consistente**:
  - Git: tag `campeao-4x4-v3_8_8`
  - Zip: `~/Downloads/suiteviagem-web-v3_8_8-campeao-4x4-20260923.zip`
  - Baseline anterior: `~/Downloads/suiteviagem-web-v3_8_1-photo-backgrounds.zip`

## 2. A FEATURE QUE FOI TESTADA E REVERTIDA ("Ver todos")

Implementação concluída e VALIDADA em **2 corridas 4×4 (PASS) + E2E Playwright (PASS)**:
- **Backend** (`module_worker_v3.py`): payloads `DONE:` enriquecidos
  - flights → `top_prices` (top 5 preços) — fonte `run_fast_search()` já retorna `top5_prices`
  - hotels → `results` (até 30: nome, price, total, currency, url, stars)
  - cars → `results` (até 30: name, supplier, price, currency, **url** — `TotalBRL` é `Decimal`, precisa de `float()`)
  - events → já tinha `results`
- **Frontend** (`suiteviagem_web.py`): botão `Ver todos →` em cada card abre **modal** com lista completa (nome, meta, preço, link externo). Close por × / overlay / ESC.
- O bug do clique (eventos/listeners) foi corrigido: container tinha `class="cards"` **sem id** → trocado para listener global `document.addEventListener('click', e => e.target.closest('.see-all'))`.

## 3. POR QUE REVERTEMOS (LEIA — ISTO É O APRENDIZADO)

Depois do fechamento, o usuário testou e **os sintomas de instabilidade voltaram**:
- **Voo falhou 2x** sob carga real do servidor (o motor, isolado, roda OK: 41,8s / R$ 267 / 142 preços).
  Causa: contenção — Chromium órfão acumulado + hotel rodando headful ao mesmo tempo → renderer do Flights estoura timeout → `DONE: ok=false`.
- **Carro** falhou 1x com `NoSuchWindowException` (driver morto no intervalo ready→search — flake recorrente de idle).
- Busca perceptivelmente **mais lenta** (o custo do 4×4 já é ~90–107s: hotel ~44s de navegação + eventos com atraso fixo de 20s).
- A base dos "4 consistentes" correu risco → **o dono do projeto decidiu REVERTER** para `campeao-4x4-v3_8_8` e encerrar o experimento.

**Regras de ouro (não repetir esses erros):**
1. **Não re-tentar a feature "Ver todos" (ou qualquer frontend) antes de resolver a instabilidade de ambiente.** O código revertido NÃO foi guardado em branch/patch — será preciso refazer (rápido, é pequeno).
2. A consistência dos 4 vem de: **isolamento** (perfil Chrome `mkdtemp` por sessão em `cars_worker_v20e.py`, `TMPDIR` por worker em `parallel_arena_v3.py:42–48`, perfis por processo em `hotels_booking.py`), **escalonamento FASE A/B** (Flights sozinho + gate 9s em `suiteviagem_web.py`), **retry/rebuild de driver** (`module_worker_v3.py:135–172`), e **fallbacks em camadas** (`google_flights_fastpath.py:14/50/136`). **Qualquer mudança que toque nesses pontos = alto risco.**
3. **Antes de rodar qualquer coisa**: limpar Chromium órfão (`~/.cache/suiteviagem/chrome_*` e processo `chromium`) e conferir `/tmp`/disco. Múltiplos Chrome ativos = voo derruba.
4. **Padrão de validação exigido**: só fechar mudança com **3 corridas 4×4 seguidas PASS**; se o voo falhar, rodar o flight isolado antes de culpar o motor.

## 4. PRÓXIMOS PASSOS SEGUROS (prioridade — resolver ANTES de frontend)

- **P0-1 Latência sem tocar nos motores**: evento `sleep(20)` fixo (`suiteviagem_web.py`, `_events_later`) → esperar Flights terminar de forma adaptativa (máx 9s). Ganho ~11s +/-.
- **P0-2 Reuso de driver do hotel**: `hotels_booking.py` — warmup não reutiliza driver na busca (`driver_reused=false`); espelhar o que o Cars faz (caiu de ~60s → ~12s).
- **P1**: reativar pytest (16/16 cars v18) + testes unitários dos helpers do Flights v3.8.x; listagem de cancelamento de busca/checkpoint incremental (pendência em `docs/interface-web-v1.md`).
- **P2**: feeds RSS + Newsboat, timers systemd, histórico/preço persistente.

## 5. LINHAS-EXATAS (arquivos e funções)

| Onde | O quê |
|---|---|
| `google_flights_fastpath.py` | `:14` fallback `[[null,<preço>]]`; `:50` `_safe_sync_playwright_start()`; `:107` diag rpc; `:136` retry `waits=(20,25,25,30)` + reload |
| `module_worker_v3.py` | `:135–172` `_driver_alive`/`_is_dead_driver`/`_rebuild`; DONE sempre emitido |
| `cars_worker_v20e.py` | `:53–60` perfil `mkdtemp` por sessão; motor v20G com `/api/v2/search/<uuid>` |
| `hotels_booking.py` | `:61–66` perfil por processo; `:81–84` anti-idle; `:250` SSR fast-path; `:492` query_matches |
| `parallel_arena_v3.py` | `:42–48` `TMPDIR` por worker; `:382–384` `_events_later` 20s; gate 9s |
| `suiteviagem_web.py` | `:450–452` resync pageshow/visibilitychange |

---

**Resumo em uma frase para o GPT-6 Astra**: *"Implementamos e validamos a feature de detalhes dos cards, mas a instabilidade de ambiente voltou (voo caiu 2x, busca lenta, carro com driver morto) — o dono optou por voltar ao campeão `campeao-4x4-v3_8_8` antes de perder a consistência. Antes de qualquer feature nova, feche os P0 de latência/estabilidade e siga a regra das 3 corridas."*