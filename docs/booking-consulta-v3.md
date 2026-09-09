# Booking: recuperação de consulta v3

O diagnóstico de 08/09 mostrou redirecionamento que perdeu destino, datas e ocupação, com formulário vazio e nenhum cartão. A causa do redirecionamento não está comprovada.

O motor aguarda cartões e parâmetros correspondentes na URL. Se os parâmetros forem perdidos, reaplica a URL original uma única vez na mesma sessão. Se ainda falhar, rejeita os resultados e salva HTML, captura e erro em data/diagnostics. Parâmetros corretos sem cartões geram erro próprio. A validação é conservadora: mudanças legítimas no formato da URL também podem exigir adaptação.

A busca rápida continua sem abrir detalhes individuais, em navegador oculto. Excel e histórico são preservados. Esta alteração não garante um tempo de resposta nem comprova funcionamento ao vivo. O próximo teste deve usar a mesma consulta do diagnóstico.

Instalação verifica a versão anterior por hash, testa o pacote antes de alterar o projeto e faz backup dos arquivos substituídos.
