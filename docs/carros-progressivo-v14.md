# Carros v14 — primeiro lote na interface

Base de retomada: 34ec866 (v13). Web usa --progressivo: lote conferido após estabilidade de três segundos e Price confirmado é normalizado e exibido antes do fim. Novas prévias substituem a lista em tela; valores são menores entre as ofertas coletadas, sem garantia de cobertura total.

Ao cancelar ou sair de Carros durante coleta, o primeiro lote conferido é preservado. Cancelamento cooperativo registra métricas; encerramento forçado pode usar a recuperação de prévia já existente no servidor. Erro de validação encerra com falha e sem resultados finais; prévias não são tratadas como sucesso.

Leitura da URL passa a ser uma por rodada, em vez de uma por cartão. Não é cache de preços. A cobertura adicional participa da assinatura de estabilidade. O coletor continua independente e o terminal sem --progressivo mantém sua saída anterior.

Histórico completo é gravado no término ou cancelamento; prévias durante coleta ficam em memória. Queda completa do servidor antes disso pode perder a prévia.

Teste aeroporto e limite 5 para comparar com a base. Para observar continuação, testar também limite 10: sair do módulo apenas depois da primeira prévia e conferir o primeiro lote no histórico. Se cinco ofertas já estiverem prontas no primeiro lote, a conclusão pode vir logo em seguida. Sem promessa de ganho específico antes do teste real. Hotéis preservado.
