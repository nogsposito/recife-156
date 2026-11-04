# Otimização das consultas

Os índices da tabela fato estão em [sql/indexes.sql](../sql/indexes.sql) e são criados no fim de cada carga, depois do `COPY`. Criar o índice depois da carga em massa é mais rápido do que mantê-lo atualizado linha a linha.

## Método

O script [src/benchmark.py](../src/benchmark.py), executado por `make benchmark`, faz quatro coisas:

1. apaga os índices e atualiza as estatísticas (`ANALYZE`);
2. roda cada consulta com `EXPLAIN (ANALYZE, BUFFERS)`: uma vez para aquecer o cache e mais 15 vezes, guardando a mediana do tempo de execução;
3. recria os índices, atualiza as estatísticas e mede de novo;
4. reescreve a tabela abaixo, junto com a forma como o PostgreSQL leu `fact_tickets` em cada caso.

Os tempos são de uma máquina local com o banco no Docker e cerca de 200 mil chamados. O valor absoluto muda de máquina para máquina; o que importa é a comparação entre as duas colunas.

## Resultados

<!-- benchmark:start -->
Índices:

| Consulta | Sem índice (ms) | Com índice (ms) | Ganho | Leitura de fact_tickets sem índice | Com índice |
|---|---|---|---|---|---|
| [Fila em aberto de um bairro, dos chamados mais antigos para os mais novos](../sql/benchmark/01_open_queue_by_neighborhood.sql) | 38,6 | 0,2 | 199,1x | Seq Scan | Index Scan (idx_fact_tickets_open_by_neighborhood) |
| [Médias móveis de 7 e 28 dias de um serviço no semestre](../sql/benchmark/02_service_moving_average.sql) | 37,9 | 3,5 | 10,9x | Seq Scan | Index Scan (idx_fact_tickets_service_opened) |
| [Chamados por dia e grupo, ao lado da chuva do dia](../sql/analyses/09_daily_tickets_and_rain.sql) | 337,1 | 332,7 | 1,0x | Seq Scan | Index Only Scan (idx_fact_tickets_service_opened) |

Reescrita, com os índices criados:

| Consulta | Primeira versão (ms) | Reescrita (ms) | Ganho |
|---|---|---|---|
| [Chamados por dia e grupo, ao lado da chuva do dia](../sql/analyses/09_daily_tickets_and_rain.sql) ([primeira versão](../sql/benchmark/03_daily_tickets_and_rain_join_first.sql)) | 822,3 | 332,7 | 2,5x |
<!-- benchmark:end -->

## O que os números mostram

O índice parcial `idx_fact_tickets_open_by_neighborhood` guarda só os chamados em aberto, cerca de um quarto da tabela, já ordenados por bairro e data. A consulta da fila de um bairro deixa de ler a tabela inteira e de ordenar o resultado: ela percorre o índice na ordem certa e para nos 50 primeiros. É a consulta que mais ganha, perto de cem vezes.

O índice `idx_fact_tickets_service_opened` (serviço e data) serve às consultas que olham um serviço ao longo do tempo, como as médias móveis. Em vez de ler os 200 mil chamados e descartar quase todos, o banco vai direto aos poucos milhares daquele serviço, em ordem de data. O ganho fica em torno de dez vezes.

A consulta de chuva por dia e grupo quase não muda com índices, e isso é esperado: ela precisa contar todos os chamados, então ler a tabela inteira continua sendo o caminho mais barato. Nela, o que funcionou foi reescrever o SQL. A primeira versão cruzava o calendário inteiro (todos os dias × todos os grupos) com cada chamado e só então contava. A versão atual conta os chamados por dia e grupo primeiro e depois completa os zeros no calendário. As duas devolvem exatamente o mesmo resultado, e a reescrita é cerca de 2,5 vezes mais rápida.

## Custos e limites

- Cada índice ocupa espaço e deixa a carga um pouco mais lenta. Os dois índices foram escolhidos pelo uso real (fila por bairro no painel operacional e séries de um serviço), não para cobrir todas as colunas.
- Com 200 mil linhas tudo já responde em menos de um segundo. O benchmark mostra a tendência que importaria com mais anos de dados, quando a leitura completa da tabela fica proporcionalmente mais cara.
- Os tempos variam alguns milissegundos entre execuções; por isso a tabela usa a mediana de 15 rodadas.
