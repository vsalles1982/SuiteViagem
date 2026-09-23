# Suíte de Viagens — Web v3.7 Champion

Integração da Arena v3.7 com interface web local clicável e resultados progressivos.

## Tela

- Passagens: azul
- Hospedagem: violeta
- Carro: verde
- Eventos: preto
- Calculadora final: marrom/café

A calculadora soma somente valores confirmados. Se um evento não tiver preço
confirmado ou não houver evento no período, aparece como “não incluído”, nunca
como R$ 0.

## Executar

Na raiz do projeto SuiteViagem:

```bash
./.venv/bin/python ~/Downloads/suiteviagem-web-v3_7-champion/suiteviagem_web.py
```

Depois abra:

http://127.0.0.1:8787

Espere “Motores quentes ✓” e clique em **Pesquisar ao vivo**.

Os valores padrão reproduzem a consulta campeã:
RIO → SAO, Petrópolis, GRU, São Paulo, 20/09/2026 → 21/09/2026.

Booking continua headful porque esse foi o modo confiável validado.


## v3.7.1 — lista interna de eventos

O cartão de Eventos mantém exatamente o mesmo tamanho visual.
A lista agora usa scroll interno, tipografia menor e mostra cada evento em linha compacta.
Isso é apenas renderização no navegador; não muda a estratégia nem o tempo dos coletores.


## v3.7.2 — Events pagination

O backend do Shotgun agora percorre a agenda em lotes de 3 páginas, busca
detalhes em paralelo e para quando:
- encontra a quantidade pedida dentro do intervalo; ou
- uma rodada inteira deixa de produzir links novos; ou
- atinge o limite de segurança de 15 páginas.

O card continua com o mesmo tamanho e scroll interno.
Os outros três módulos e a orquestração campeã v3.7 não foram alterados.
