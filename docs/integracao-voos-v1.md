# Google Flights no histórico — etapa 5

Base: 35f2185. Novos adaptador, comando e testes. O motor gerar_feeds_voos.py é carregado diretamente da instalação; nenhum seletor ou rotina de geração RSS é alterado.

```bash
./.venv/bin/python -m suiteviagem.voos --origem RIO --destino SAO --horizonte 7 --intervalo 1 --nome "Rio x SP" --rss
./.venv/bin/python -m suiteviagem historico --modulo flights
```

O horizonte é contado a partir da data de execução no computador. O motor inicia daqui a cinco dias; horizonte 7/intervalo 1 corresponde a três datas (hoje+5, hoje+6, hoje+7). Não significa partida fixa em 12/09. Só ida é o padrão; --ida-volta --duracao 7 pesquisa retorno sete dias após cada partida.

Cada sucesso vira flight_date_quote: menor preço reconhecido naquela data, em BRL/centavos. Não é um voo identificado. Companhia, número, passageiros e classe ficam desconhecidos. Rota/datas são os parâmetros enviados; o adaptador não confirma independentemente a seleção do site. Horário de observação representa o retorno da coleta porque o motor não retorna instante por data.

Taxas desconhecidas mantêm total_minor nulo. A cobertura complete_for_scope significa somente todas as datas amostradas com resposta. Falhas por data ficam no histórico, com tentativas registradas; resultados válidos são preservados e estado failed identifica a falha parcial.

--rss é opcional. Com nome "Rio x SP", o motor atualiza ~/feeds_voos/rio_x_sp.xml, o feed já usado pelo Newsboat. Sem preços, preserva o RSS anterior. Falha de exportação gera aviso e mantém os resultados no banco. O histórico conserva execuções anteriores; o RSS representa a última atualização dessa rota. RSS não é registrado na tabela artifacts nesta etapa.

Cancelamento antes do retorno do motor registra cancelled, mas não recupera preços ainda em memória no coletor. Persistência incremental e execução progressiva são trabalhos posteriores, assim como layout e otimização de tempo.

28 testes locais passaram (21 existentes e 7 novos): centavos/ordenação/reabertura, ida e volta, falha parcial, ausência de preços, RSS com sucesso/falha, cancelamento/entrada inválida e data duplicada. Testes usam respostas controladas; busca real e RSS real serão validados na máquina do usuário.
