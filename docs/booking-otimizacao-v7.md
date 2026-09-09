# Hotéis v7 — reduzir trabalho antes do primeiro lote

Base v6 preservada no pacote anterior: usuário observou primeiro lote em 40s e 20s em duas consultas. Não é média controlada.

Mudanças:
- pandas carregado na exportação, depois das prévias; geopy somente quando houver cálculo de distância no modo avançado.
- ChromeDriver reaproveitado somente após conferir versão do Chromium, caminho dentro do cache padrão .wdm e compatibilidade major/minor/build do executável. Atualização ou cache inválido usa webdriver-manager habitual. Metadados locais em data/chromedriver-booking.json, sem cookies nem preços.
- URL e cartões são lidos no mesmo snapshot JavaScript, retirando uma chamada Selenium a cada ciclo de leitura.
- /api/state omite o primeiro lote e o registro bruto da prévia apenas na resposta HTTP. A cópia integral em memória continua disponível para recuperação no cancelamento. Prévia já recebida não é retransmitida.
- polling da busca ativa em 500ms, 1500ms em repouso. Mais requisições leves em troca de menor atraso de entrega.
- driver_seconds e navigation_seconds separam inicialização do navegador e abertura/espera. first_batch_seconds continua incluindo a abertura, total_seconds inclui Excel.

Mantidos: validação de consulta, três segundos de estabilidade, 12 segundos sem novos cartões, limite de 45 segundos de leitura, preços por estadia, taxas desconhecidas identificadas, Xvfb e cancelamento, modo avançado, histórico e Excel. Não há redução proposital da cobertura nesta versão.

Validação: 53 testes locais, API de estado, atualização e corrupção do cache de driver, snapshot de URL e retenção dos dados de auditoria. Instalação com backups e repetição verificadas. JavaScript com sintaxe verificada. Execução no Booking ainda depende do teste real do usuário. Não há tempo garantido.

## Próxima medição
Executar três buscas com mesmo destino, datas, ocupação e modo, sem outra coleta ativa. Registrar primeiro lote observado na tela, driver_seconds, navigation_seconds, first_batch_seconds, total_seconds e número de ofertas. A primeira pode criar o índice do driver. As seguintes devem mostrar ChromeDriver local conferido. Preços podem mudar entre buscas.

## Possibilidades avaliadas para etapas separadas
Cache de resultados: pode acelerar consultas repetidas, mas exige identificação de dado antigo, chave completa e política de atualização. Não implementado.
Navegador persistente: pode reduzir inicialização, mas mantém RAM ocupada e exige isolamento/reinício e tratamento de falhas. Não implementado.
Rolagem mais curta ou primeiros N cartões: pode reduzir tempo final, mas omitir ofertas mais baratas. Não implementado.
Mudanças na estratégia de carregamento/bloqueio de recursos: precisam de experimento isolado; os testes anteriores mostraram sensibilidade do fluxo. Não alteradas.
Resultados por SSE: polling atual é suficiente para este teste local; só substituir se a entrega HTTP medida justificar.
Detalhes sob demanda e exportação em tarefa separada: detalhes já fora do modo rápido e Excel já depois das prévias. Ganho potencial no término, não na primeira oferta.

A calculadora/roteiro não está conectada. Estas otimizações se restringem a hotéis; outros coletores preservados.
