# ADR 0002: Camadas bronze, silver e gold

Status: aceito

## Contexto

Na primeira versão, o pipeline lia os CSVs, limpava em memória e carregava o banco de uma vez. Funcionava, mas qualquer mudança na limpeza exigia baixar tudo de novo, não havia como olhar o dado entre as etapas e uma falha no meio não deixava rastro do que já tinha sido processado.

## Decisão

Separar o pipeline em camadas com responsabilidades fixas:

- landing (`data/raw`): os arquivos exatamente como chegam das fontes;
- bronze (Parquet): o mesmo conteúdo, sem nenhuma correção, mais colunas de origem e data de ingestão;
- silver (Parquet): chamados limpos, padronizados e deduplicados, clima tipado, prontos para análise;
- gold (PostgreSQL): esquema estrela modelado para consulta, com índices.

Entre silver e gold há uma barreira de qualidade: se uma validação grave falha, a gold não é tocada.

## Consequências

- Mudar uma regra de limpeza só exige reprocessar a partir da bronze, sem novo download.
- A ingestão pode ser incremental: o manifesto da bronze registra a versão de cada arquivo, e só o que mudou é baixado de novo.
- Cada camada pode ser inspecionada isoladamente, o que ajuda a depurar e a explicar o tratamento.
- Há mais arquivos e mais código do que no pipeline direto. Para o tamanho do projeto, a organização compensa.
