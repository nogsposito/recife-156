# ADR 0001: PostgreSQL como banco da camada gold

Status: aceito

## Contexto

As análises, o dashboard e as próximas etapas (modelo de ML e assistente que gera SQL) precisam de um banco que responda consultas analíticas, seja fácil de subir em qualquer máquina e use SQL padrão de mercado. O volume é de centenas de milhares de linhas, não de bilhões.

## Decisão

Usar PostgreSQL 16 em Docker Compose como banco da camada gold.

## Alternativas consideradas

- DuckDB: muito rápido para análise sobre Parquet e sem servidor, mas não atende bem várias conexões simultâneas (dashboard, notebooks e pipeline) nem permissões por usuário, que o assistente de SQL vai precisar.
- SQLite: simples, mas com poucas funções analíticas e sem controle de acesso.
- Data warehouse em nuvem (BigQuery, Snowflake): exagerado para o volume e impede rodar o projeto do zero sem conta paga.

## Consequências

- Window functions, CTEs, percentis, índices parciais e `EXPLAIN ANALYZE` ficam disponíveis, e o benchmark de otimização é feito no mesmo banco que serve o dashboard.
- O projeto depende de Docker para rodar sem instalar nada além dele.
- Para um volume muito maior, a camada gold poderia migrar para um banco colunar sem mudar bronze e silver.
