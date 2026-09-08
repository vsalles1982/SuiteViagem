# SuiteViagem — base de integração 0.1.0

Entrega inicial do plano de 08/09/2026. Base do projeto: fb26c72.

Implementado: contrato JSON v1, BRL em centavos, histórico SQLite e migração inicial, consultas/resultados, eventos de transição, repetição por parent_query_id, recuperação explícita de interrupção e backup consistente. Usa somente biblioteca padrão do Python.

Os coletores ainda não estão conectados. A demo grava quatro consultas FICTÍCIAS com cobertura parcial, uma por módulo, sem abrir navegador ou consultar fornecedores.

## Instalação e execução

Execute instalar.py com o Python da .venv, passando a raiz da SuiteViagem. O instalador testa antes de copiar e recusa conflitos. Não altera os motores. Cria data/.gitignore para excluir dados gerados do Git.

Na raiz do projeto:

```bash
./.venv/bin/python -m suiteviagem demo
./.venv/bin/python -m suiteviagem --db data/suiteviagem-demo.sqlite3 historico
./.venv/bin/python -m suiteviagem --db data/suiteviagem-demo.sqlite3 consulta UUID_EXIBIDO
./.venv/bin/python -m unittest discover -s tests -p test_integration_history.py -v
```

Cada demo acrescenta quatro registros. Banco real padrão: data/suiteviagem.sqlite3. A demo usa suiteviagem-demo.sqlite3; informe --db para consultar esse histórico. Caminhos padrão partem da instalação.

Backup para arquivo ainda inexistente:

```bash
./.venv/bin/python -m suiteviagem --db data/suiteviagem-demo.sqlite3 backup data/demo-backup.sqlite3
```

## API

new_query(module, requested, parent_query_id=None) cria documento em fila. History.create persiste; start inicia; finish grava resultados e estado final em uma transação. get recupera; list filtra por módulo; backup usa API SQLite.

finish aceita resultados parciais em failed/cancelled/interrupted ou succeeded. Finalizado é imutável: repetir exige novo query_id. money('189.67') retorna 18967; floats são rejeitados. Taxas desconhecidas mantêm total nulo. Parâmetros e detalhes específicos ficam em objetos JSON.

recover_interrupted é explícito e só deve ser chamado pelo futuro serviço após confirmar ausência de worker ativo. Comandos de leitura não encerram trabalhos.

## Testes e limites

Sete testes locais em Python 3.12 passaram: centavos inválidos; reabertura dos quatro módulos e backup; taxas; consultas vazias/falhas/canceladas/interrompidas; imutabilidade/repetição; rollback; chaves estrangeiras e versão futura de banco. O instalador repete os testes com o Python do usuário; compatibilidade local com 3.14 ainda precisa dessa confirmação.

Próxima entrega: adaptador real de eventos. Pendentes: validação específica de cada fornecedor, filtros por destino/período, progresso de coleta, persistência incremental, API de artefatos (tabela preparada), exportações comuns, fila/worker, API web e interface aprovada. Os CSV/Excel antigos não são importados automaticamente.
