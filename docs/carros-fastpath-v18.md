# Carros fast path v18 — resolver geral de localização

## Mudança
A v18 generaliza o fast path validado na v17 para locais fora de FLN usando o schema real do endpoint DiscoverCars:
- `placeID` -> `location_id`
- `cityID` -> `city_id`
- `countryID` -> `country_id`

O resolver preserva ambiguidade: cidade pura escolhe somente a opção `(all locations)`; um aeroporto nunca é inferido arbitrariamente. Código IATA explícito tem prioridade. Se o endpoint retornar uma única opção, ela é aceita.

## Cache
Locais resolvidos com sucesso são gravados em `~/.cache/suiteviagem/discovercars_locations.json`. O arquivo versionado do projeto não é alterado em runtime.

## Segurança
Toda busca criada continua validando a URL canônica/sq, IDs, datas, residência BR e idade 35. Qualquer falha cai no formulário v12.1.

## Evidência usada
Diagnóstico real de 10/09/2026: Rio de Janeiro, Galeão, São Paulo, Guarulhos, Paris e New York retornaram HTTP 200 e o schema `placeID/cityID/countryID`.
