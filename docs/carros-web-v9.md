# Carros web v9 — início da otimização

Hotéis v8 aprovado pelo usuário e preservado byte a byte no motor e no adaptador.
Carros roda no display virtual X11 pelo servidor, com o coletor independente preservado.
Local ambíguo retorna opções estruturadas gravadas no histórico. O usuário escolhe uma opção, confere datas e inicia nova consulta; não há escolha automática de aeroporto.
A tentativa ambígua permanece registrada como failed, sem preços, com código location_choice_required.

Esta etapa ainda não adiciona resultados progressivos aos carros, nem promete redução de tempo. Validar em busca real um local exato e um local ambíguo; conferir retirada, devolução e CSV. Se houver bloqueio por cookies, enviar o erro e diagnóstico gerado em resultados_carros.

Próxima etapa: medir inicialização, navegação e primeiro preço confirmado; aplicar extração em lote e prévias aos carros preservando a conferência da consulta e da ordenação Price.
