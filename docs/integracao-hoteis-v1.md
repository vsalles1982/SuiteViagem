# Booking no histórico — etapa 4

Base: 878f12b. O motor recebe opção return_records=True para devolver registros, caminho Excel e URL enviada. O retorno padrão de run_scraping e a GUI permanecem compatíveis. Não há alteração de seletores ou otimização de tempo.

```bash
./.venv/bin/python -m suiteviagem.hoteis --destino "Petrópolis" --checkin 2026-09-12 --checkout 2026-09-13
./.venv/bin/python -m suiteviagem historico --modulo hotels
```

Busca com dois adultos, zero crianças e um quarto. Continua coletando todos os cartões carregados e visitando detalhes. Histórico real em data/suiteviagem.sqlite3. Excel continua sendo gerado pelo coletor na pasta de execução.

Preços normalizados diretamente do texto em BRL usando centavos inteiros; soma de impostos explícitos, total nulo quando taxas desconhecidas. Sem preço mantém a hospedagem. Estrelas ausentes ficam nulas, separadas da avaliação dos hóspedes. Endereço, quarto, texto da estadia e registro original ficam preservados.

Os parâmetros enviados são registrados em requested. O adaptador não confirma independentemente a seleção efetiva do site: effective.confirmed_parameters fica nulo. A cobertura permanece partial. A base stay_total descreve o uso do preço do cartão nesta busca; o texto Stay Text é preservado para conferência das condições.

Cancelamento/falha são registrados. Antes do retorno do motor não há salvamento incremental dos cartões. Falha de exportação impede o retorno estruturado nesta versão. Falha individual na normalização preserva os outros registros e encerra com failed. Esses limites serão tratados nas próximas evoluções do serviço.

21 testes locais (base, eventos, carros e hotéis) passaram com dados controlados; quatro testes novos cobrem taxas, centavos/moeda, reabertura/preço ausente e falha/cancelamento/ocupação divergente. Busca real no navegador será validada na máquina do usuário. Instalador confere hash do motor anterior e faz backup antes da substituição.
