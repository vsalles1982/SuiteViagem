# Plano B — proposta externa preservada

Origem: sugestão Grok encaminhada pelo usuário em 10/09/2026.

Proposta: separar abertura, digitação, espera estável e confirmação do local; contar redigitações; depois, se os números apontarem custo de polling, ler campo e sugestões juntos em uma chamada JavaScript.

A instrumentação foi incorporada à v15 com duas adaptações: as subetapas são aninhadas para não encerrar location_seconds; o contador é escrito imediatamente em métricas, inclusive quando há exceção, sem mudar o retorno da função.

## Alternativa reservada, ainda não implementada

1. Avaliar 3–5 consultas equivalentes se o primeiro diagnóstico não for conclusivo.
2. Se a espera dominar, experimentar leitura conjunta do valor do campo e das sugestões em uma chamada JS por verificação.
3. Preservar filtros de visibilidade/modal ativo, até duas recuperações e confirmação exata do local solicitado.
4. Comparar falhas, primeiro lote e tempo total sob condições semelhantes, usando navegador novo em cada consulta.
5. Reverter a alternativa se houver regressão de validação ou estabilidade.

Não reduzir estabilidade de preços, reutilizar sessão, trocar automaticamente aeroporto nem remover validações para obter números menores. Ganhos precisam ser medidos; diferenças de rede e do fornecedor permanecem possíveis.
