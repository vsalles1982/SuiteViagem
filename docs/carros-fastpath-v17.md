# Carros fast path v17 — create-search direto com fallback v12.1

## Objetivo
Promover para o módulo real a arquitetura validada nos benchmarks de 10/09/2026:

1. resolver IDs do local sem preencher o formulário;
2. chamar `POST /api/v2/search/create-search`;
3. abrir exatamente a URL canônica retornada pelo backend;
4. detectar estabilidade com snapshot JS atômico;
5. usar janela de 1,5 s;
6. fazer scroll quando necessário para materializar novas ofertas;
7. manter o formulário v12.1 como fallback automático.

## Segurança
O caminho rápido só é aceito quando a URL retornada passa pelos validadores existentes de
`sq`, datas, PickupLocationId, DropOffLocationId, residência BR e idade 35. Qualquer falha
na resolução/API cai no fluxo visual v12.1 já existente.

## Local validado em cache inicial
- Florianopolis Airport (FLN), Florianopolis, Brazil
- location_id: 5594
- city_id: 5542
- country_id: 13

Para locais não presentes no cache, o motor tenta o endpoint público de autocomplete. Se não
conseguir resolver de forma única e completa, usa o fallback v12.1.

## Coleta
A estabilidade deixou de depender de objetos WebElement, evitando
`StaleElementReferenceException`. O snapshot JS é usado apenas para decidir quando o DOM
estabilizou; a extração final continua usando o parser e os validadores rígidos existentes.

## Baseline experimental anterior à integração
Benchmark v3: 5/5 execuções concluídas, mediana total 17,066 s no cenário FLN, com create-search
direto, URL canônica, 1 scroll e estabilidade 1,5 s.

## Testes de regressão no snapshot
16 testes passaram: adapter, timings, progresso, calendário e escolhas.
