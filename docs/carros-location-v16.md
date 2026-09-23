# Carros v16 — menos chamadas na retirada

Base de instalação: v15. As métricas novas da v15 continuam disponíveis.

- Leitura de elementos visíveis em uma chamada JavaScript por seletor durante a retirada, excluindo campos sem caixa, ancestrais ocultos e modais inativos.
- Reutilização do elemento que acabou de receber o clique; remoção da espera duplicada pelo campo móvel. O próprio clique mantém espera e tentativas por erro de interação.
- Preenchimento inicial em um único comando nativo send_keys: Control+A, liberação de Control, Backspace e texto. Não atribui value via JavaScript.
- Recuperação de texto perdido permanece com até duas tentativas. Confirmação exata do local, sugestões estáveis por 2 s e preços estáveis por 3 s mantidos.
- Calendário, hotéis, interface, sessão nova e exportações preservados.

## Evidência que motivou o ajuste

Consulta v15 f6343726-a845-4ed0-98e0-974ebe914808: abertura 14.240 s, digitação 8.320 s, espera estável 3.761 s, confirmação 1.024 s, zero redigitações. Primeiro lote 77.513 s; motor 82.767 s. Isso aponta os alvos, mas não prova que chamadas ao navegador expliquem toda a demora.

## Validação

76 testes locais com simulações. Novos casos verificam exclusão de campos ocultos/modal inativo e sequência de teclas com Control liberado. Execução real do DiscoverCars depende do teste do usuário; nenhum ganho de segundos é garantido.

Instalador cria backups dos arquivos alterados e recusa versões divergentes. Testar a mesma consulta: Florianopolis Airport (FLN), 13–14/09/2026, cinco ofertas; comparar JSON, especialmente location_open, location_type, first_batch, total e location_redigits. Se houver falha, enviar JSON e diagnóstico. Plano B externo mantido em carros-plano-b-grok.md.
