# DiscoverCars no histórico — etapa 3

Base: 7bfdcbe. O motor agora oferece coletar_ofertas com retorno estruturado e callback de log. A função da TUI continua chamando o mesmo serviço. Seletores, calendário, validação sq e ordenação Price foram preservados.

Comando:

```bash
./.venv/bin/python -m suiteviagem.carros --local "Ibiza Airport" --retirada 2026-09-12 --devolucao 2026-09-13 --limite 5
./.venv/bin/python -m suiteviagem historico --modulo cars
```

Também aceita URL em --local. Por nome: horários 11h, residência BR, idade 35 e mesmo local. Pode ser necessário fechar cookies ou confirmar Price se a seleção automática falhar; siga o log do navegador.

Banco real: data/suiteviagem.sqlite3. O motor continua exportando seu CSV. Total anunciado fica em amount_minor com base rental_total e em details.advertised_total_minor. total_minor fica nulo porque o motor não discrimina impostos; cobertura opcional não equivale a impostos incluídos. Horários são locais sem fuso identificado. Links/condições são conferidos novamente pelo adaptador.

Histórico registra falhas e cancelamento. Nesta etapa o serviço só devolve ofertas após concluir a coleta/exportação; falha ou cancelamento anterior ao retorno não preserva cartões em memória no banco. Se houver erro de normalização, registros já convertidos podem ser preservados. Progresso persistente e recuperação incremental são futuros.

17 testes locais passaram, incluindo base, Shotgun e quatro casos de carros: centavos/reabertura, moeda incorreta, condições divergentes, falha/cancelamento. Compilação Python verificada. Navegador real e TUI após a refatoração precisam da validação na máquina do usuário.

O instalador valida o motor anterior pelo hash e cria backup antes de substituí-lo. Outros arquivos existentes diferentes causam recusa. Nenhuma otimização de tempo foi feita nesta etapa.
