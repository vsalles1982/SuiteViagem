# Correção v12.1

A v12 enviava segundos decimais em coverage.metrics, cujo contrato permite somente inteiros. Isso impedia History.finish e deixava a consulta running. Testes usavam relógio com valores inteiros e não detectaram essa falha.

Adaptador agora converte segundos para milissegundos inteiros, com nomes *_milliseconds e unit milliseconds. Log do motor continua em segundos. Contrato comum preservado. Teste usa 6,125 segundos e verifica 6125 milissegundos gravados em sucesso, falha, cancelamento e erro de normalização.

Reparo opcional e idempotente de um registro conhecido via suiteviagem.reparar_carros_v12, com servidor parado. Nenhuma oferta é inventada ou apagada.
