# Booking no display virtual — v5

O teste real anterior retornou 52 hospedagens em 72,24 segundos com Chromium normal no Xvfb. O modo headless=new não ficou comprovado.

Agora o servidor inicia hotéis via xvfb-run com display automático, autenticação gerenciada pelo wrapper, resolução 1920x1080x24 e TCP desativado. O processo remove WAYLAND_DISPLAY/WAYLAND_SOCKET e força ozone-platform=x11 apenas nas opções do navegador dessa execução. O coletor independente continua disponível. Nenhum perfil pessoal é reutilizado.

Requisitos no Arch: xorg-server-xvfb e xorg-xauth. A falta desses executáveis gera erro antes de iniciar a consulta. O modo rápido e o avançado usam display virtual; a interface e o contrato de resultados continuam iguais.

Cancelamento envia SIGINT ao grupo da busca. Após oito segundos sem saída, envia SIGTERM; depois de três segundos, SIGKILL. O wrapper xvfb-run gerencia o display no término. Encerramentos forçados podem impedir a finalização do registro SQLite; não marcar consultas anteriores como interrompidas automaticamente enquanto outro coletor puder estar ativo.

Validação: 44 testes locais, incluindo construção do comando, ausência de dependências, regressões dos módulos e encerramento de um processo real que ignora sinais. O fluxo Chromium/Xvfb iniciado pelo site e o cancelamento durante uma busca real ainda precisam ser verificados na máquina do usuário.

Esta versão não implementa resultados progressivos nem altera tempos da coleta. Consultas mantêm cobertura parcial.
