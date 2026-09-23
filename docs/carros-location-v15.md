# Carros v15 — diagnóstico da retirada

Base: distribuição v14.1. Instrumentação, sem alteração intencional do comportamento da coleta.

## Métricas no JSON de coverage.metrics

| Nome | Unidade | Mede |
| --- | --- | --- |
| location_open_milliseconds | milliseconds | Espera pelo campo, abertura do seletor e clique inicial |
| location_type_milliseconds | milliseconds | Preenchimento inicial |
| location_wait_stable_milliseconds | milliseconds | Espera da lista, incluindo eventuais redigitações |
| location_select_confirm_milliseconds | milliseconds | Escolha e confirmação exata do local |
| location_redigits | count | Tentativas adicionais iniciadas: 0, 1 ou 2 |

As quatro durações estão CONTIDAS em location_milliseconds. Não somar novamente ao total. Na execução bem-sucedida sua soma coincide com location_milliseconds, salvo arredondamento de poucos milissegundos. Em uma falha, somente subetapas iniciadas aparecem; a ativa é encerrada ao entrar no diagnóstico ou na limpeza. Contador ausente significa que a espera instrumentada não foi iniciada; não significa zero.

O contador é atualizado antes de tentar redigitar. Portanto inclui tentativa iniciada mesmo se o clique ou a digitação lançar uma exceção. A função continua retornando somente as opções, mantendo compatibilidade com os chamadores existentes.

Mantidos: estabilidade das sugestões em 2 segundos, estabilidade dos preços em 3 segundos, até duas recuperações de texto, navegador novo por busca, validações de local/datas/preço e resultados progressivos. Hotéis e interface não foram alterados.

## Validação e uso

74 testes locais passaram, incluindo contagem em sucesso/erro e preservação de métricas no histórico em sucesso, falha e cancelamento. São testes locais com simulação; execução real do fornecedor ainda necessária.

Instalador valida arquivos contra a v14.1 antes de copiar, cria backup e permite repetição idêntica. Arquivos divergentes são preservados e interrompem a instalação.

Repetir FLN, 13–14/09/2026, 11h, Brasil, idade 35, limite 5. Enviar o JSON após concluir. Comparar primeiro os tempos; preços podem variar. A v15 não promete reduzir a espera: identifica o gargalo para o próximo ajuste.
