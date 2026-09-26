# TAREFA GPT-6 ASTRA — Feature "GERE SEU LINK E VOE!!!" (Link da Viagem)

> Regras iguais à rodada anterior (que passou nas 3 corridas). Siga exatamente, não rebaixe a régua.

## CONTEXTO / ESTADO ATUAL (confie, não re-explore)
- Repo: `/home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem`
- Base atual: commit `2f3179a`, tag **`campeao-4x4-v3_9-detalhes`** (com a feature "Ver todos" já commitada: `<dialog id="detailsModal">`, botões `.see-all[data-module=...]`, payloads `top_prices`/`results`, `car_details()`, hotéis com `results` só em search).
- Servidor web: `suiteviagem_web.py`, porta 8787. Frontend é uma string HTML/CSS/JS embutida no arquivo.
- Formulário tem os inputs com ids: `fo` (origem voo), `fd` (destino voo), `hc` (cidade hotel), `cl` (local carro), `ec` (cidade evento), `start`, `end`. Botão buscar tem id `go`. Estado de prontidão: `ready`/`pollReady()`/`$('go').disabled`.
- Pilares de estabilidade dos "4 consistentes" (NÃO RETOQUE): isolamento de perfil Chrome/TMPDIR, escalonamento FASE A/B + gate 9s, retry/rebuild de driver, fallbacks do Flights.
- Você NÃO tem execução nem acesso a arquivos: os arquivos estarão anexados. Entregue os **arquivos completos** ou **diffs git-style** prontos para colar.

## OBJETIVO (único)
Feature **"Link da Viagem"**: sem cadastro, sem email — qualquer busca vira um link; quem abrir cai na MESMA viagem e ela já **dispara sozinha**.

1. **Botão "🔗 Link da viagem"** ao lado do botão Buscar. Ao clicar, monta a URL pública com os valores atuais dos inputs e copia pro clipboard:
   `http://127.0.0.1:8787/?fo=RIO&fd=SAO&hc=Petropolis&cl=GRU&ec=Sao+Paulo&start=2026-11-07&end=2026-11-08&run=1`
   (use `encodeURIComponent`; copie via `navigator.clipboard` com fallback `textarea+execCommand`; dê feedback visual tipo "Link copiado ✓").
2. **Abrir o link** → capítulo na inicialização do script: se `location.search` tiver `fo`/`fd`/`hc`/`cl`/`ec`/`start`/`end` (pelo menos os obrigatórios), **preenche os inputs** (com `decodeURIComponent`). Se tiver `run=1`, **dispara a busca automaticamente** — aguardando os motores ficarem prontos (o `pollReady()` já re-checa; chame o fluxo do botão `go` UMA vez quando `ready`).
3. **Copy/tagline**: no topo da página, adicionar o subtítulo **"Sem cadastro, sem email… gere seu link e voe!"** (estilo do subtítulo existente, sem quebrar o layout).
4. **Não** criar banco/rota nova: o link é stateless (a consulta vive no URL). Não mexa no modal "Ver todos" nem nos payloads.

## ACEITE (todos obrigatórios)
1) 3 corridas 4×4 consecutivas com `ok=true` nos 4 módulos e mesmos padrões de preço (sem regressão);
2) wall time ≤ baseline atual (~61–65s);
3) E2E Playwright:
   a. abrir `/?fo=RIO&fd=SAO&hc=Petropolis&cl=GRU&ec=Sao+Paulo&start=2026-11-07&end=2026-11-08&run=1` → inputs preenchidos + busca dispara sozinha + 4 módulos concluem + modal "Ver todos" funciona;
   b. clicar "🔗 Link da viagem" → clipboard contém URL que reproduz os campos;
4) só o `suiteviagem_web.py` alterado (HTML/CSS/JS embutido). Se precisar de outro arquivo, justifique;
5) nada dos pilares mudado. Se algo falhar: pare, diagnostique e reporte — não rebaixe a régua.

## ENTREGA
Arquivos completos/diffs prontos para colar, zero pedido de acesso a disco, e ao final: `git diff --stat` + resultado das 3 corridas (quem roda a validação é o usuário).