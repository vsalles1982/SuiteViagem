# Recuperação pelo formulário Booking

O diagnóstico mostrou calendário funcional com data-date e destino vazio após digitação. Não comprovou a causa do esvaziamento ou redirecionamento.

Esta versão substitui a repetição da URL pelo preenchimento do formulário quando os parâmetros são perdidos. Seleciona datas, confere seleção, digita destino com até duas tentativas e confere retenção antes de enviar. Não escolhe sugestões ambíguas. A busca por texto fica sujeita à resolução do site. Só aceita cartões com parâmetros correspondentes na URL; não comprova individualmente a localização de cada propriedade.

A recuperação é conservadora: datas não acessíveis/confirmadas, reformatação do destino ou alteração dos parâmetros podem encerrar a consulta com erro. Calendários longos além dos meses visíveis na conferência também podem exigir adaptação. Diagnóstico automático, histórico, Excel, modo rápido e navegador oculto são preservados.

Testes locais simulam interação, falha e proteção contra dados incorretos. Não substituem o teste real no Booking. Não há prazo de resposta garantido.
