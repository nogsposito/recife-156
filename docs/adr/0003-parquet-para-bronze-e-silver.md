# ADR 0003: Parquet para bronze e silver

Status: aceito

## Contexto

As camadas intermediárias precisam guardar centenas de milhares de linhas, ser lidas rápido pelo pandas e manter os tipos (datas, inteiros com nulos) entre uma etapa e outra. Os CSVs do portal têm separador `;`, encodings diferentes entre anos e tudo como texto.

## Decisão

Gravar bronze e silver em Parquet, com pyarrow, particionando a bronze por ano (`year=2024/data.parquet`).

## Alternativas consideradas

- CSV: legível, mas perde os tipos, ocupa mais espaço e traz de volta os problemas de separador e encoding.
- Tabelas no próprio PostgreSQL: funcionaria, mas misturaria dado bruto com o modelo de consulta e tornaria o reprocessamento mais lento.
- Delta Lake ou Iceberg: oferecem versionamento e transações, mas são pesados demais para um projeto local deste tamanho.

## Consequências

- Os arquivos de silver ficam bem menores que os CSVs e são lidos em segundos, com os tipos preservados.
- O particionamento por ano casa com a ingestão incremental: um ano novo ou alterado reescreve só a sua pasta.
- Parquet não é legível em editor de texto; para inspecionar, usa-se pandas ou DuckDB.
