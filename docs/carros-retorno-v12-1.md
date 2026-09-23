# Retorno ao motor de carros v12.1

O scraper_carro/discovercars.py é uma cópia byte a byte da distribuição v12.1. A versão v12 original teve erro de contagem; por isso a referência usada é a v12.1, com métricas inteiras corrigidas.

Medição histórica da consulta FLN: motor 48,591 s; primeiro lote identificado internamente em 44,029 s. Isso não é garantia para outra execução. Naquela versão o lote ainda não era enviado à interface durante a coleta.

O adaptador atual reconhece que o motor antigo não aceita on_progress e chama sua assinatura original. Portanto carros exibe resultados no final; o fluxo progressivo de hotéis, interface e histórico permanecem. Em carros, cancelamento antes do final não preserva lote parcial do motor antigo.

Os testes de funções removidas (sugestões em lote, redigitação e preenchimento v16) são arquivados com sufixo .bak e os testes de tempos/progresso ajustados ao motor restaurado. 66 testes locais passaram. Motor conferido por SHA-256 contra v12.1. Backup de cada arquivo substituído e dos testes arquivados, sem apagar dados.

Instalação destinada à v16, com recusa de arquivos divergentes. Não executar durante consulta. Depois testar o mesmo aeroporto FLN, 13–14/09/2026, cinco ofertas, e enviar o JSON.
