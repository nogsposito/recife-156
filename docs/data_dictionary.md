# Dicionário de dados

## Fonte

| Item | Valor |
|---|---|
| Conjunto | [Central de Atendimento de Serviços da Emlurb (156)](https://dados.recife.pe.gov.br/dataset/central-de-atendimento-de-servicos-da-emlurb-156) |
| Publicador | Prefeitura do Recife (dados da Emlurb, disponibilizados pela Emprel) |
| Licença | Open Database License (ODbL) |
| Acesso | API CKAN (`package_show`) para listar os arquivos; download de um CSV por ano |
| Granularidade | um chamado por linha, com a última situação conhecida |
| Anos usados por padrão | 2024 e 2025 (configurável pela variável `YEARS`, a partir de 2024) |

## Schema real dos arquivos (2024 em diante)

Os CSVs usam `;` como separador e têm 13 colunas, todas lidas como texto e tipadas na limpeza. Os percentuais de vazios foram medidos nos arquivos de 2024 (108.082 linhas) e 2025 (114.653 linhas).

| Coluna original | Coluna limpa | Tipo final | Descrição | Observações |
|---|---|---|---|---|
| `GRUPOSERVICO_CODIGO` | `group_code` | inteiro | Código do grupo de serviço | 24 grupos em 2024 e 2025 |
| `GRUPOSERVICO_DESCRICAO` | `group_name` | texto | Nome do grupo (ex.: ILUMINACAO PUBLICA) | Um código corresponde sempre ao mesmo nome |
| `SERVICO_CODIGO` | `service_code` | inteiro | Código do serviço | 110 serviços distintos nos dois anos |
| `SERVICO_DESCRICAO` | `service_name` | texto | Nome do serviço (ex.: MANUTENCAO EM LAMPADA APAGADA) | Cada serviço pertence a um único grupo |
| `LOGRADOURO` | `street` | texto | Tipo e nome da via (ex.: `RUA  do Chacon`) | Espaços duplicados entre tipo e nome |
| `NUMERO` | `street_number` | texto | Número do imóvel | Preenchido com espaços à direita; usa `SN`, `S/N` e textos como `TODA VIA` |
| `BAIRRO` | `neighborhood` | texto | Bairro | 96 valores nos dois anos, incluindo `BAIRRO NAO INFORMADO` (54 linhas) e `INDEFINIDO` |
| `RPA` | `rpa` | inteiro (1 a 6) | Região Político-Administrativa | Quatro bairros aparecem com duas RPAs em poucas linhas |
| `DATA_DEMANDA` | `opened_on` | data | Data de abertura do chamado | Sem valores inválidos; há chamados abertos desde 2008 |
| `SITUACAO` | `status` | texto | Última situação do chamado | Ver valores abaixo |
| `DATA_ULT_SITUACAO` | `status_updated_on` | data | Data da última mudança de situação | Sempre dentro do ano do arquivo e nunca anterior à abertura |
| `latitude` | `latitude` | decimal | Latitude do endereço | Vazia em 77% das linhas de 2024 e 50% de 2025; 57 pontos fora do Recife (ex.: 85,05) |
| `longitude` | `longitude` | decimal | Longitude do endereço | Mesmo padrão da latitude (ex.: -180) |

Valores de `SITUACAO` encontrados: `CADASTRADA`, `PREPARACAO`, `EXECUCAO`, `PENDENCIA`, `FISCALIZACAO` e `ATENDIDA`. O portal não documenta o significado de cada etapa; o projeto trata `ATENDIDA` como chamado resolvido e todas as outras como chamado em aberto.

## Particularidades encontradas

Cada arquivo anual é uma foto do fim daquele ano. O arquivo de 2025 traz todos os chamados cuja última mudança de situação aconteceu em 2025, inclusive chamados abertos em anos anteriores (9.560 linhas abertas antes de 2025). Por isso o mesmo chamado aparece em mais de um arquivo, com situações diferentes: 3.034 chamados do arquivo de 2025 também estão no de 2024, a maioria passando de `EXECUCAO` ou `CADASTRADA` para `ATENDIDA`.

Não existe identificador do chamado. O projeto reconhece o mesmo chamado em anos diferentes pela combinação de serviço, logradouro, número, bairro e data de abertura. Linhas com a mesma combinação dentro de um mesmo arquivo (cerca de 2% das linhas) são tratadas como chamados distintos, e o pareamento entre arquivos segue a ordem de aparição.

O portal lista 2024 e 2025 duas vezes. Os dois recursos de 2025 são diferentes (um vai até setembro e o outro cobre o ano inteiro), então a ingestão escolhe, para cada ano, o recurso modificado mais recentemente.

Os arquivos até 2023 seguem outro padrão: códigos de grupo e serviço numerados de outra forma (o código 20 é LIMPEZA URBANA em 2023 e COLETA URBANA em 2024), acentos removidos na origem (`PREPARAO`, `REMOO DE ENTULHOS`), bairros em maiúsculas com espaços de preenchimento e linhas quebradas por aspas. Juntar esses anos exigiria um mapeamento manual de serviços, por isso o recorte começa em 2024.

## Regras de limpeza

| Problema | Tratamento | Onde |
|---|---|---|
| Espaços de preenchimento e duplicados | `strip` e espaços únicos | `clean_tickets`, `normalize_text` |
| Acentos e caixa diferentes entre anos | Texto em maiúsculas, sem acentos | `normalize_text` |
| Bairro não informado | `BAIRRO NAO INFORMADO` e `INDEFINIDO` viram nulo | `clean_neighborhood` |
| Número sem valor | `SN`, `S/N` e vazio viram nulo | `clean_street_number` |
| Coordenadas fora do Recife | Nulas fora da caixa lat [-8,20; -7,90] e lon [-35,05; -34,80] | `clean_coordinates` |
| Linhas sem código, data de abertura ou situação | Descartadas (nenhuma nos arquivos atuais) | `clean_tickets` |
| Linhas idênticas no mesmo arquivo | Removidas (49 em 2024 e 39 em 2025, após a padronização) | `clean_tickets` |
| Mesmo chamado em vários arquivos | Mantida só a versão mais recente | `deduplicate_snapshots` |
| Chamados abertos antes do recorte | Descartados | `combine_snapshots` |
| Bairro com mais de uma RPA | Fica com a RPA mais frequente | `build_tables` |

## Modelo relacional (PostgreSQL)

Definido em [sql/schema.sql](../sql/schema.sql) e recriado a cada carga.

| Tabela | Coluna | Tipo | Descrição |
|---|---|---|---|
| `service_groups` | `group_code` | integer, PK | Código do grupo |
| | `group_name` | text | Nome do grupo |
| `services` | `service_code` | integer, PK | Código do serviço |
| | `service_name` | text | Nome do serviço |
| | `group_code` | integer, FK | Grupo ao qual o serviço pertence |
| `neighborhoods` | `neighborhood_id` | integer, PK | Identificador do bairro |
| | `neighborhood_name` | text, único | Nome padronizado |
| | `rpa` | smallint (1 a 6) | Região Político-Administrativa |
| `tickets` | `ticket_id` | bigint, PK | Identificador gerado na carga |
| | `service_code` | integer, FK | Serviço pedido |
| | `neighborhood_id` | integer, FK | Bairro (nulo quando não informado) |
| | `street`, `street_number` | text | Endereço |
| | `opened_on` | date | Data de abertura |
| | `status` | text | Última situação conhecida |
| | `status_updated_on` | date | Data da última mudança de situação |
| | `days_to_last_update` | integer, gerada | `status_updated_on - opened_on`; para chamados `ATENDIDA` é o tempo de resolução |
| | `latitude`, `longitude` | double precision | Coordenadas válidas ou nulas |
| | `source_year` | smallint | Arquivo anual de onde veio a versão mais recente |
