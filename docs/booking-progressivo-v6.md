# Booking progressivo — v6

Base preservada: checkpoint v5, testado pelo usuário com 52 hotéis em 1min13s pelo site.

Modo rápido lê os cartões com uma chamada JavaScript por amostra. Confere nome, preço, taxas, estadia e quarto estáveis por três segundos. Envia o primeiro lote antes da primeira rolagem, depois substitui as prévias por amostras conferidas. Preços alterados ou cartões removidos saem da prévia até nova estabilização. São menores preços encontrados até agora, não todos os hotéis nem garantia de menor preço global.

Abertura e validação da consulta continuam iguais. Rolagem após primeiro lote, a cada 2,5 segundos; parada por 12 segundos sem crescimento ou limite de 45 segundos. O resultado final inclui apenas registros com preço estável. Campos sem confirmação permanecem desconhecidos.

As prévias trafegam do subprocesso ao servidor por mensagens JSON identificadas e são exibidas pelo polling de 1,5s. Primeiro lote fica separado das atualizações em memória. Histórico SQLite final é gravado no término. Ao mudar de módulo durante coleta de hotéis, o cliente solicita cancelamento; primeiro lote é salvo como consulta cancelada com cobertura parcial. Se o worker for encerrado antes de finalizar, servidor tenta finalizar apenas aquele registro ainda running com a cópia do primeiro lote. Não altera consultas finais. Uma queda abrupta de todo o servidor antes de persistir pode perder prévias.

Trocar de módulo aguarda o encerramento da busca antiga para liberar a próxima: continua havendo uma busca ativa por vez. Abrir fornecedor não cancela coleta. Não há integração com calculadora/roteiro ainda. Nenhuma oferta é escolhida automaticamente para uma reserva.

Excel é gerado para a coleta concluída. Cancelamento preserva primeiro lote no histórico/JSON, sem gerar Excel parcial. Erros de validação não são convertidos em sucesso.

Novo timing first_batch_seconds inclui abertura, contado desde início do motor. Log adicional de primeiro lote mede somente a partir da leitura dos cartões. UI mede tempo total desde o início do subprocesso. Não há promessa de latência.

50 testes locais: regressões, estabilidade de preço/taxa, desaparecimento de cartões, primeiro lote antes da rolagem, histórico no cancelamento, resultado final e comunicação da prévia. Sintaxe JavaScript verificada. Fluxo real com fornecedor e experiência visual progressiva ainda precisam do teste do usuário.

Instalador confere versão anterior por hash e faz backup. Para voltar a v5, use os backups gerados para os arquivos substituídos; instalador antigo não sobrescreve arquivos novos diferentes automaticamente.
