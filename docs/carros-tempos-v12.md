# Carros v12 — medir antes de otimizar

Base validada e enviada ao Git: 48dfd4d. Esta versão registra tempos; não reduz esperas nem adiciona prévias.

Etapas exclusivas: validation, driver, navigation, location, dates, submit, results_wait, sorting, collection, export, diagnostic (se falhar), cleanup. Sufixo _seconds em cada métrica.
first_batch_seconds: acumulado desde início do coletor até o primeiro lote confirmado, ainda sem exibição progressiva. total_seconds: inclui encerramento do navegador; não inclui inicialização do Python/Xvfb nem gravação do adaptador no SQLite.

Tempos ficam em coverage.metrics no JSON e no andamento detalhado. Preservados em exceções e cancelamento cooperativo; encerramento forçado do processo pode impedir gravação. Tempo ausente significa etapa não alcançada, não zero.

Teste primeiro com aeroporto exato e limite 5; envie JSON. Se houver outra consulta genérica para selecionar aeroporto, seu tempo pertence a outro registro. Não comparar a soma dessas tentativas com uma busca direta.

Validações de datas, preço e ordenação preservadas. Hotéis v8 e interface v10 preservados.
