# CHECKPOINT — DiscoverCars v18 + Warm Driver validado

Data: 2026-09-11

## Estado congelado

- Fast path v18 generalizado para múltiplos aeroportos/cidades via autocomplete real do DiscoverCars.
- Schema real confirmado: `placeID`, `cityID`, `countryID`.
- Fallback v12.1 preservado.
- 16/16 testes de regressão verdes após instalação da v18.
- GRU e GIG validados no caminho `create-search` direto, com 5/5 ofertas.
- Benchmark com Chromium persistente validou arquitetura de browser quente.

## Resultados principais

### Antes, navegador frio
- GRU: ~61.21 s
- GIG: ~52.21 s

### Warm driver — um único Chromium reutilizado
- Boot único do Chromium: ~12.05 s
- GRU-1: ~15.87 s
- GIG-1: ~11.69 s
- GRU-2: ~11.73 s
- GIG-2: ~11.53 s
- Mediana das 4 buscas: ~11.71 s
- Sucesso: 4/4

## Conclusão

A arquitetura vencedora para a futura v19 web é:

`servidor web -> Xvfb persistente -> Chromium persistente -> fast path v18 -> reinício automático apenas em falha`

Não integrar isso ao servidor sem preservar este checkpoint.

## SHA da v18 instalada

`a3ebbc3f2744c7af555b91555e89697882d49a8a4eb6c75f74c83b07fbc62cd6`

## Próximo passo

Implementar v19 web com worker persistente e comparar o tempo percebido em `http://127.0.0.1:8765/` contra o baseline anterior.
