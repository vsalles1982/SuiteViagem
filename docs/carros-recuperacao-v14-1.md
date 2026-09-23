# Carros v14.1 — conferir texto antes das sugestões

Diagnóstico 20260909-235653-982518: TimeoutException em sugestoes_estaveis; HTML e imagem mostram PickupLocation vazio, sem itens de autocomplete. O código já havia enviado o texto, mas não verificava se ele permanecia. A causa do esvaziamento não é demonstrada pelo snapshot.

Durante a espera, reler o campo atual. Se o texto divergir do solicitado, redigitar até duas vezes usando teclas normais. Reiniciar a estabilidade das sugestões a cada perda de texto; exigir dois segundos de lista estável com o texto conferido. Usar a mesma janela de espera, sem ciclo infinito. A escolha final continua exigindo correspondência exata.

Prévia de preços, datas, ordenação e hotéis preservados. Testar aeroporto exato e enviar JSON; em falha, novo diagnóstico.
