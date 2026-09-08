# Shotgun integrado — etapa 2

Base: ff66392. Novos arquivos: suiteviagem/adapters, suiteviagem/shotgun.py e tests/test_shotgun_adapter.py. O motor shotgun_terminal_estavel.py é carregado da instalação e permanece intacto.

Execução na raiz:

```bash
./.venv/bin/python -m suiteviagem.shotgun --cidade "São Paulo" --inicio 2026-09-12 --fim 2026-09-13 --limite 5
./.venv/bin/python -m suiteviagem historico --modulo events
./.venv/bin/python -m suiteviagem consulta UUID_DA_CONSULTA
```

Usa data/suiteviagem.sqlite3, separado da demo. Uma consulta é criada antes de carregar o motor e acessar a rede. Falhas são registradas; eventos já normalizados são preservados ao cancelar com Ctrl+C. Uma interrupção forçada do processo ainda depende de recuperação posterior, sem gravação incremental nesta etapa.

O adaptador reutiliza download, paginação, JSON-LD, fuso, endereço, organizador e lineup do motor. Controla a iteração de eventos para preservar resultados parciais. O preço estruturado replica as regras de disponibilidade e janela de venda: SoldOut excluído, InStock/LimitedAvailability considerados. BRL em centavos, taxas desconhecidas, unidade lote. Moedas diferentes permanecem nos dados de origem, sem conversão. Datas sem fuso são rejeitadas.

Cada evento guarda source_event e lote selecionado. O hash SHA256 identifica o arquivo do coletor utilizado. O limite significa subconjunto; os resultados são ordenados por início local. Falhas de rede em parte da consulta produzem estado failed com resultados parciais visíveis. Sem preço conhecido não significa indisponibilidade confirmada.

A cidade é validada pela regra atual do motor (título da agenda); não é uma resolução geográfica independente. O motor ainda limita a agenda a 15 páginas. Nenhuma promessa de todos os eventos ou dos menores preços da cidade.

Verificação: 13 testes locais passaram (7 da base e 6 do adaptador) com respostas simuladas. Casos: esgotado versus disponível; janela futura; moeda; preço zero; limite; reabertura; falha e cancelamento com retenção; vazio; cidade inválida; data sem fuso. A consulta real deve ser validada na máquina do usuário. Não foi executada busca ao vivo nesta entrega.

Este comando grava JSON normalizado no banco; exportação CSV/JSON independente e TUI anterior continuam pelos comandos antigos. API de artefatos, fila e interface web continuam em etapas futuras.
