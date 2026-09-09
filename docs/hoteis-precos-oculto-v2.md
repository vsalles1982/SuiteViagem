# Hotéis — preços dos cartões e navegador oculto

A busca completa anterior visitava cada página para endereço/coordenadas, além de aguardar 60 segundos sem cartões novos. A captura do usuário mostrava 4min07s no hotel9/52. Esta entrega separa preços e detalhes.

Na interface, Hospedagem inicia em “Preços e taxas dos cartões”: navegador headless, sem visitar páginas individuais. Endereços e coordenadas ficam ausentes e marcados como não consultados. Excel e histórico continuam. A opção “Consulta completa com endereços” mantém visitas individuais e é mais demorada, também sem janela na interface.

Modo de preços: espera de 12 segundos sem novos cartões e janela de rolagem de 45 segundos, mais estabilização dos preços por 3 segundos (até15s). Não é limite do tempo total: abertura do navegador, rede, extração e exportação adicionam tempo. Pode omitir ofertas que carregariam depois; cobertura permanece parcial. Não promete encontrar o menor preço de todo o site.

O Chromium usa --headless=new. Isso oculta a janela, não garante rapidez nem evita desafios do fornecedor. Se o site exigir interação, a coleta pode falhar e a falha é registrada; não abre janela automaticamente. Para diagnóstico visual pelo terminal, omita --oculto. Não há contorno de CAPTCHA.

Comando equivalente:

```bash
./.venv/bin/python -m suiteviagem.hoteis --destino "Petrópolis" --checkin 2026-09-13 --checkout 2026-09-14 --rapido --oculto
```

O comando antigo, sem flags, preserva consulta completa com navegador visível. A estratégia de carregamento eager aguarda o documento inicial, seguida das esperas explícitas por cartões. Referências: [Selenium headless](https://www.selenium.dev/blog/2023/headless-is-going-away/) e [opções de carregamento](https://www.selenium.dev/documentation/webdriver/drivers/options/).

Tempos open_seconds, cards_seconds, details_seconds, export_seconds e total_seconds aparecem no log e no histórico. Eles permitem comparar o próximo teste à consulta anterior; headless e rede reais ainda precisam de validação na máquina do usuário.

33 testes locais passaram, incluindo modo oculto/completo nos argumentos, flag headless e execução da rotina rápida com verificação de que fetch_details não é chamada. Python compilado e JavaScript validado. Sem teste de navegador real nesta entrega.

Instale somente após a busca atual terminar e encerrar o servidor com Ctrl+C. O instalador confere os hashes dos arquivos da versão anterior, faz backup dos alterados e permite reinstalação idêntica. Reinicie o servidor e atualize a página para carregar a nova interface. Esta atualização afeta Booking; DiscoverCars ainda usa navegador visível nesta etapa.
