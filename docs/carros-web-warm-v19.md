# DiscoverCars v19 web — worker quente persistente

## Objetivo

Levar para `http://127.0.0.1:8765/` a arquitetura validada pelo benchmark warm-driver:

- um Xvfb persistente;
- um Chromium persistente;
- engine v18 generalizado intacto;
- várias consultas reaproveitando navegador/cache/conexões;
- reinício do worker em falha ou cancelamento.

## Segurança arquitetural

A v19 NÃO substitui `suiteviagem/web/server.py`.
Ela adiciona:

- `suiteviagem/cars_worker.py`
- `suiteviagem/web/server_v19.py`

O servidor congelado continua disponível a qualquer momento:

```bash
./.venv/bin/python -m suiteviagem.web.server
```

A v19 é iniciada por:

```bash
./.venv/bin/python -m suiteviagem.web.server_v19
```

Ambos usam `http://127.0.0.1:8765/`; execute somente um deles por vez.

## Como testar

1. Inicie `server_v19`.
2. Aguarde no terminal:
   `Carros v19: Chromium persistente aquecido em ...s.`
3. Abra `http://127.0.0.1:8765/`.
4. Faça uma busca de GRU com 5 carros.
5. Faça GIG.
6. Repita GRU.
7. Compare o tempo percebido.

Baseline warm-driver validado antes da integração:
- GRU quente: ~11,73 s
- GIG quente: ~11,53 s
- mediana: ~11,71 s

A interface web acrescentará algum overhead de job/history/polling, portanto o alvo inicial é ~12–20 s percebidos.
