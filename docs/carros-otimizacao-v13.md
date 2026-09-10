# Carros v13 — leitura das sugestões em lote

Base medida (22c20ea6): 5 ofertas; local 13,275 s; primeiro lote 44,029 s; total motor 48,591 s. Consulta encerrada sem erro.

Substitui várias chamadas Selenium por opção por uma única leitura JavaScript da lista visível. Mantém dois segundos de estabilidade da lista, escolha exata de local, clique Selenium e confirmação após seleção. Modais inativos e ancestrais ocultos são excluídos. Não guarda cache de preços ou de sugestões.

Sem alterações nos hotéis, datas, ordenação, preços e exportação. Primeiro lote ainda não é mostrado progressivamente. O ganho real depende do próximo teste e não foi medido neste ambiente.

Repetir mesmo aeroporto, datas e limite 5; enviar JSON. Comparar location_milliseconds e first_batch_milliseconds, considerando variação de rede e carregamento do fornecedor.
