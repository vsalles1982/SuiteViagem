# Hotéis v8 — exportação direta

Tempos reportados v7: Excel 12,82s em Jericoacoara; 9,98s em Gramado; 10,89s em Petrópolis. Essa etapa inclui carregamento das bibliotecas, preparação, gravação e publicação do arquivo; não é evidência de que toda a demora venha do pandas.

V8 remove pandas do coletor de hotéis e usa gravação direta: XlsxWriter se disponível, senão openpyxl. Mantém todas as colunas, ordem crescente por total/preço, valores numéricos, cabeçalho e publicação por arquivo temporário seguida de os.replace. Texto é gravado literalmente, inclusive se começar com sinal de igual.

Não altera coleta, estabilidade, cobertura, modo avançado, Xvfb, prévias e cancelamento. Atua após as prévias, visando término mais rápido, não antecipação do primeiro lote. Não implementa navegador persistente nem cache de ofertas.

54 testes locais passaram, incluindo arquivos reais gerados com os dois exportadores e inspeção de células numéricas, textos, cabeçalhos e ausência de fórmulas indevidas. A instalação é repetível e guarda backups v7. Não há medição na máquina do usuário ainda.

Teste: repetir uma busca concluída com as mesmas condições, anotar export_seconds, total_seconds e conferir Excel. Consultas canceladas continuam sem relatório completo de tempos, pois motor não retorna o relatório final nesse fluxo.
