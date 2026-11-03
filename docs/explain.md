# Como cada componente funciona

Para cada parte do projeto: o que faz, por que foi escolhida e que alternativas existiam.

## Fontes e ingestão

### API CKAN do Portal de Dados Abertos (`src/ingestion/ckan.py`)

O que faz: lista os arquivos do conjunto do 156, escolhe o mais recente de cada ano e baixa só os que mudaram desde a última execução.
Por que: o portal é CKAN, e a API diz a versão de cada arquivo, o que permite a ingestão incremental. O portal lista alguns anos duas vezes, e a API mostra qual é o mais novo.
Alternativas: baixar URLs fixas (quebra quando o portal republica um ano) ou usar a busca do datastore (testada; a opção de valores distintos devolve um único registro, então não serve).

### API histórica do Open-Meteo (`src/ingestion/weather.py`)

O que faz: baixa chuva e temperatura diárias do Recife, um ano por vez, e guarda o JSON original.
Por que: gratuita, sem chave, com histórico diário e resposta em JSON, que também alimenta o MongoDB.
Alternativas: INMET ou APAC (pluviômetros reais, mais precisos, mas com acesso menos estável e formatos variados). O Open-Meteo estima a chuva por modelo em grade, limitação registrada no notebook 03.

### Cliente HTTP com novas tentativas (`src/ingestion/http.py`)

O que faz: repete as chamadas que dão timeout ou erro temporário, esperando mais a cada vez.
Por que: as duas APIs públicas falharam durante o desenvolvimento, uma delas travando a execução por quase duas horas.
Alternativas: tratar cada erro na mão, ou bibliotecas de retry como tenacity (desnecessária, o urllib3 já traz `Retry`).

## Camadas de dados

### Landing, bronze e silver em Parquet (`src/layers`)

O que faz: landing guarda os arquivos como chegaram; bronze, o mesmo conteúdo em Parquet com colunas de origem; silver, os chamados limpos e o clima tipado.
Por que: separar o bruto do tratado permite reprocessar sem baixar de novo e inspecionar cada etapa. Parquet preserva os tipos e é muito mais rápido e compacto que CSV. Detalhes nos ADRs 0002 e 0003.
Alternativas: tudo no PostgreSQL (mistura bruto e modelado), CSV intermediário (perde tipos), Delta Lake ou Iceberg (pesados para um projeto local).

### Manifesto da bronze

O que faz: registra, por arquivo, a versão publicada e o hash do conteúdo, para decidir o que precisa ser processado de novo.
Por que: é o que torna a ingestão incremental e idempotente sem depender de banco.
Alternativas: comparar datas de arquivo (frágil) ou uma tabela de controle no banco (cria dependência do banco já na ingestão).

### Limpeza (`src/transform/cleaning.py`)

O que faz: tipa, padroniza textos, anula placeholders e coordenadas inválidas e mantém só a versão mais recente de cada chamado.
Por que: cada regra vem de um problema real encontrado no notebook 01, e está em código testado para que pipeline e notebook usem a mesma lógica.
Alternativas: limpar dentro do notebook (não reprodutível) ou no SQL depois da carga (mais difícil de testar).

### Validações de qualidade (`src/quality/checks.py`)

O que faz: doze checagens sobre a silver; falha grave interrompe antes da gold, alerta só registra.
Por que: impede que um arquivo quebrado no portal chegue ao dashboard sem ninguém perceber.
Alternativas: Great Expectations ou Pandera (mais recursos, mais dependências e configuração para doze regras simples).

## Bancos

### PostgreSQL com esquema estrela (`sql/schema.sql`)

O que faz: guarda a gold, com `fact_tickets` e as dimensões de serviço, bairro e data (com o clima do dia), recriada a cada carga em uma transação.
Por que: SQL padrão de mercado, window functions, índices parciais e `EXPLAIN ANALYZE`, controle de acesso por usuário (usado pelo assistente). ADR 0001.
Alternativas: DuckDB (excelente para análise, fraco para várias conexões e permissões), SQLite (poucas funções analíticas), data warehouse em nuvem (custo e conta).

### Índices e benchmark (`sql/indexes.sql`, `src/benchmark.py`)

O que faz: dois índices escolhidos pelo uso real e um script que mede as consultas pesadas com e sem eles.
Por que: mostrar com números quando o índice ajuda (fila de um bairro, cem vezes mais rápida) e quando não ajuda (agregação da tabela inteira, que melhorou com reescrita).
Alternativas: indexar todas as colunas filtradas (custo de espaço e carga sem ganho medido).

### Schema `ops` (`sql/ops.sql`)

O que faz: guarda o histórico de execuções e de validações.
Por que: permite saber quando cada carga rodou, o que mudou e por que falhou.
Alternativas: só logs em arquivo (somem e não se consultam) ou uma ferramenta de orquestração como Airflow ou Dagster (exagerada para um pipeline que roda em um comando).

### MongoDB (`src/nosql/raw_store.py`)

O que faz: guarda cada linha bruta dos arquivos anuais e cada resposta do Open-Meteo inteira, em documentos, com agregações de exemplo.
Por que: o dado bruto tem formato que pode mudar e estrutura aninhada (o JSON do clima tem metadados e listas paralelas); um banco de documentos guarda isso sem esquema fixo e permite investigar a fonte antes de mudar a limpeza.
Alternativas: só a bronze em Parquet (já guarda o bruto, mas não se consulta sem código), JSONB no PostgreSQL (funcionaria, misturando bruto e modelado no mesmo banco).

## Análise

### Consultas SQL versionadas (`sql/analyses`)

O que faz: dez consultas analíticas com CTEs, window functions, percentis e médias móveis, usadas pelos notebooks e pelo dashboard.
Por que: SQL em arquivo é revisável, testável no banco e reaproveitado em vários lugares.
Alternativas: SQL escrito dentro do notebook (duplicado e difícil de revisar) ou um ORM (esconde exatamente o SQL que se quer mostrar).

### Notebooks (`notebooks`)

O que faz: contam cada etapa como uma investigação: a pergunta, o dado, o achado e a decisão.
Por que: tornam o raciocínio auditável; a lógica fica em `src/` e é importada, sem duplicar código.
Alternativas: só relatórios gerados por script (perdem o raciocínio) ou só código (perde a narrativa).

### Gráficos estáticos (matplotlib, `src/analysis/charts.py`)

O que faz: os gráficos do README e dos notebooks, com uma paleta única validada para daltonismo.
Por que: imagens leves que funcionam no GitHub.
Alternativas: Plotly também nos notebooks (interativo, mas não renderiza no GitHub) ou seaborn (mais um estilo para manter).

## Produto

### Dashboard (Streamlit e Plotly, `app/`)

O que faz: cinco páginas: operacional, gerencial, estratégica, previsões e o assistente.
Por que: Streamlit permite um dashboard completo só em Python, ao lado do resto do código; Plotly dá interação (hover, zoom) sem esforço.
Alternativas: Power BI ou Metabase (sem código, mas fora do repositório e difíceis de versionar), Dash (mais flexível, mais código).

### Modelo de 30 dias (scikit-learn, `src/ml`)

O que faz: prevê, na abertura, a chance de o chamado ser atendido em até 30 dias, com validação temporal e dois baselines.
Por que: gradient boosting do scikit-learn lida bem com categorias e valores faltantes, treina em segundos e não exige dependência extra.
Alternativas: LightGBM ou XGBoost (ganho marginal neste tamanho), regressão do número de dias (enviesada pelos chamados ainda abertos), modelos de sobrevivência (mais adequados ao problema, mais difíceis de explicar e operar).

### NLP das descrições de serviço (`src/nlp`)

O que faz: põe as descrições antigas na taxonomia atual e sugere o serviço equivalente, comparando embeddings de um transformer multilíngue com n-gramas de caracteres.
Por que: é o único texto dos dados, e unificá-lo destrava 12 anos de histórico. O modelo `paraphrase-multilingual-MiniLM-L12-v2` é pequeno o bastante para rodar em CPU.
Alternativas: correspondência aproximada de strings (rápida, mas não entende sinônimos), um LLM para fazer o de-para (bom resultado provável, com custo e menos reprodutibilidade).

### Assistente "Pergunte aos dados" (API da Anthropic, `src/ai`)

O que faz: o Claude escreve a SQL a partir da pergunta, consulta o banco por uma ferramenta e responde em português, mostrando a SQL.
Por que: o laço de ferramenta deixa o modelo corrigir as próprias consultas, e o controle da execução fica no código do projeto. A validação com sqlglot entende a estrutura da SQL, em vez de procurar palavras proibidas.
Alternativas: LangChain ou LlamaIndex (mais camadas para um único laço), validação por expressão regular (fácil de contornar), deixar o modelo responder sem consultar (inventaria números).

## Engenharia

### Docker Compose e Makefile

O que faz: um comando sobe PostgreSQL, MongoDB, pipeline, treino e dashboard; o Makefile dá atalhos para cada etapa.
Por que: qualquer pessoa roda o projeto sem instalar Python nem bancos.
Alternativas: ambiente virtual local (depende da máquina), Kubernetes (desnecessário para uma máquina).

### Testes, lint e integração contínua (pytest, ruff, GitHub Actions)

O que faz: 46 testes de lógica pura, sem banco nem internet; ruff para estilo e formatação; o GitHub Actions roda tudo em todo pull request.
Por que: os testes cobrem as regras que mais podem errar em silêncio (limpeza, deduplicação, incremental, validação de SQL).
Alternativas: testes de integração com banco no CI (mais lentos, valem para uma próxima etapa), flake8 e black (o ruff faz os dois).

### Organização do trabalho (issues, Kanban, pull requests)

O que faz: cada etapa tem milestone, issues no quadro e um pull request com commits pequenos e semânticos.
Por que: deixa o histórico legível e mostra o que foi feito, em que ordem e por quê.
Alternativas: commits direto no `main` (sem revisão nem rastreabilidade).
