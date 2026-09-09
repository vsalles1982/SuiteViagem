# Suíte de Viagens — interface local v0.2

Base: ab18cd6. Execute na raiz:

```bash
./.venv/bin/python -m suiteviagem.web.server
```

Abra http://127.0.0.1:8765 no navegador. Deixe o terminal aberto; Ctrl+C encerra o servidor e solicita parada da busca ativa. Não configura serviço de inicialização automática. Porta alternativa: --port 8766.

## Entrega

Navegação Voos, Hospedagem, Carros, Eventos e Histórico; cores azul, violeta, verde, preto e café. Formulários ligados aos quatro comandos existentes. Busca em processo separado, uma ativa por vez, sem bloquear a página. Progresso textual, tempo decorrido, cancelamento e logs. Histórico real existente, filtro por módulo, reabertura de consultas, preços/condições, links dos fornecedores e download do documento JSON.

Interface de trabalho com tema escuro, cabeçalho Suíte de Viagens, resumo lateral e buscas recentes. Ajusta a disposição em telas menores. Usa fontes monoespaçadas disponíveis no sistema; não baixa fontes ou imagens externas.

## Funcionamento

Servidor Python local com biblioteca padrão, sem novas dependências e sem publicação na internet. Bind 127.0.0.1; valida Host e token de requisição com Origin para mutações. Comandos são listas de argumentos, sem shell. Apenas arquivos estáticos explicitamente permitidos são servidos. Texto externo é inserido como texto, não HTML. Banco: data/suiteviagem.sqlite3. Interface consulta até 300 registros recentes.

A escolha de biblioteca padrão mantém esta primeira entrega executável na .venv atual. É um servidor para uso local individual, não uma implantação pública. Não foi adicionado FastAPI nesta etapa.

Buscas reais criam seus próprios registros pelo adaptador existente. A página detecta o UUID nos logs e abre o resultado ao finalizar. Fechar a aba não encerra a busca; manter servidor aberto e reabrir recupera o andamento. Estado de acompanhamento é em memória do servidor; histórico concluído está no SQLite. Não execute várias instâncias do servidor para a mesma base.

Cancelamento envia SIGINT somente ao grupo de processos da busca criada pelo servidor. Ao encerrar o servidor, há espera limitada e encerramento do seu grupo se necessário. Finalização forçada pode deixar consulta running no histórico; recuperação explícita e checkpoint incremental continuam pendentes. O navegador de automação pode precisar de interação com cookies ou confirmação descrita no log.

## Limites desta versão

Os resultados aparecem quando o motor retorna. Progresso não é percentual inventado. Não há aceleração da raspagem, paralelismo entre módulos, cache de consultas, execução incremental ou estimativa de tempo restante. Esses trabalhos precisam de medições e testes específicos, especialmente hotéis (761,7s na busca anterior).

Disponíveis hoje: buscas, acompanhamento, consultas anteriores e JSON. Favoritos, roteiro, comparação, exportação comum Excel, botão de repetição e configuração completa de ocupação ainda não foram implementados. Excel e RSS existentes continuam pelos comandos originais; a tela de voos não atualiza RSS automaticamente.

Campos por motor mantêm os limites existentes: hotéis dois adultos/um quarto; carros por nome 11h, BR, idade35, mesmo ponto; voos por códigos/horizonte com início daqui a5dias. A interface exibe cobertura e condições desconhecidas.

## Verificação

30 testes locais passaram: os 28 anteriores e dois novos testes cobrindo composição de comandos, leitura do histórico pelo HTTP, retorno de consulta, bloqueio de Host externo, token/Origin e caminho não permitido. JavaScript passou por node --check e Python por compilação. Instalação sobre o pacote anterior e repetição sem mudanças foram verificadas.

Validação visual e busca ponta a ponta no navegador do usuário ainda pendentes. Comece abrindo uma consulta já existente no histórico, depois teste Eventos ou Carros.
