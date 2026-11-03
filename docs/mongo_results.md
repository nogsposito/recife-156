# MongoDB: os dados brutos

O PostgreSQL guarda o dado tratado e modelado. O MongoDB guarda o dado como ele chegou, em documentos: cada linha dos arquivos anuais do 156, com os nomes de coluna e os textos originais, e cada resposta da API do Open-Meteo inteira, com os metadados e as listas diárias aninhadas. Ele serve para auditar e investigar a fonte sem esquema fixo: quando o portal muda uma coluna ou a API muda o formato, o bruto continua cabendo e pode ser consultado antes de qualquer ajuste na limpeza.

A carga ([src/nosql/raw_store.py](../src/nosql/raw_store.py)) roda no `docker compose up`, depois do pipeline, e é incremental: usa o manifesto da bronze e só recarrega um ano quando o arquivo dele mudou. As consultas abaixo são agregações do próprio MongoDB, geradas a cada carga.

<!-- mongo:start -->
Mesmo chamado em dois arquivos anuais (as 6 mudanças de situação mais comuns):

| Chamados | Situação no arquivo mais antigo | Situação no mais novo |
|---|---|---|
| 1496 | EXECUCAO | ATENDIDA |
| 635 | CADASTRADA | ATENDIDA |
| 402 | PREPARACAO | ATENDIDA |
| 123 | CADASTRADA | PREPARACAO |
| 95 | PENDENCIA | ATENDIDA |
| 33 | EXECUCAO | PENDENCIA |

Linhas brutas com coordenadas, por arquivo:

| Arquivo | Linhas | Com coordenadas | % |
|---|---|---|---|
| 2024 | 108082 | 24812 | 23.0 |
| 2025 | 114653 | 57088 | 49.8 |

Chuva por mês, a partir do JSON bruto do clima:

| Mês | Dias acima de 10 mm | Chuva (mm) |
|---|---|---|
| 2024-01 | 0 | 41.9 |
| 2024-02 | 5 | 143.9 |
| 2024-03 | 5 | 124.2 |
| 2024-04 | 3 | 129.2 |
| 2024-05 | 1 | 120.1 |
| 2024-06 | 4 | 196.8 |
| 2024-07 | 4 | 154.4 |
| 2024-08 | 0 | 89.3 |
| 2024-09 | 0 | 72.7 |
| 2024-10 | 0 | 34.8 |
| 2024-11 | 0 | 46.8 |
| 2024-12 | 0 | 75.3 |
| 2025-01 | 4 | 110.2 |
| 2025-02 | 3 | 111.3 |
| 2025-03 | 2 | 103.2 |
| 2025-04 | 0 | 63.3 |
| 2025-05 | 7 | 272.7 |
| 2025-06 | 7 | 195.7 |
| 2025-07 | 3 | 153.6 |
| 2025-08 | 3 | 175.2 |
| 2025-09 | 1 | 106.6 |
| 2025-10 | 1 | 89.0 |
| 2025-11 | 0 | 29.6 |
| 2025-12 | 0 | 49.1 |
<!-- mongo:end -->

A primeira consulta mostra, no dado bruto, o problema que o notebook 01 encontrou: o mesmo chamado aparece em dois arquivos com situações diferentes. A contagem fica perto dos cerca de 3 mil chamados da silver, mas não é igual, porque aqui as chaves só têm os espaços cortados, sem a padronização de texto da limpeza.
