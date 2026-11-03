import os
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic
import pandas as pd
from sqlalchemy import Engine, create_engine, text

from src.ai.sql_guard import ALLOWED_TABLES, MAX_ROWS, UnsafeQueryError, validate_sql

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
ASSISTANT_DATABASE_URL = os.getenv(
    "ASSISTANT_DATABASE_URL",
    "postgresql+psycopg://assistant_readonly:assistant@localhost:5433/recife156",
)
MAX_STEPS = 5

RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": (
        "Executa uma única consulta SELECT no PostgreSQL dos chamados do 156, com usuário "
        f"somente leitura, e devolve até {MAX_ROWS} linhas em CSV. Use para qualquer número "
        "que a resposta precise."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"sql": {"type": "string", "description": "Uma consulta SELECT"}},
        "required": ["sql"],
        "additionalProperties": False,
    },
    "strict": True,
}

INSTRUCTIONS = """Você responde perguntas sobre os chamados do 156 da Emlurb, a central de \
serviços urbanos do Recife, consultando o banco com a ferramenta run_sql.

Como trabalhar:
- Consulte o banco para todo número que for citar; não invente valores.
- Escreva SQL do PostgreSQL usando só as tabelas e colunas descritas abaixo.
- Prefira agregar no SQL em vez de trazer linhas soltas.
- Responda em português do Brasil, em poucas frases, com os números principais e o período.
- Se a pergunta não puder ser respondida com estes dados, diga isso e explique o que falta.

Significado dos dados:
- Cada linha de fact_tickets é um chamado, com a última situação conhecida.
- status = 'ATENDIDA' é chamado resolvido; is_open indica os que seguem na fila.
- days_to_last_update é o número de dias entre a abertura e a última mudança de situação; \
para chamados atendidos é o tempo de atendimento.
- RPA é a Região Político-Administrativa (1 a 6). Textos estão em maiúsculas e sem acento.
- v_tickets já junta chamado, serviço, grupo, bairro e RPA e costuma ser o caminho mais simples.
"""


def has_credentials() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def get_readonly_engine() -> Engine:
    return create_engine(ASSISTANT_DATABASE_URL)


# Columns of the allowed tables, plus the values of the short categorical columns, so the
# model writes SQL against what really exists
def describe_schema(engine: Engine) -> str:
    columns_sql = text(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY(:tables) "
        "ORDER BY table_name, ordinal_position"
    )
    with engine.connect() as connection:
        columns = pd.read_sql(columns_sql, connection, params={"tables": sorted(ALLOWED_TABLES)})
        groups = pd.read_sql(text("SELECT DISTINCT group_name FROM dim_service"), connection)
        statuses = pd.read_sql(text("SELECT DISTINCT status FROM fact_tickets"), connection)
        period = connection.execute(
            text("SELECT MIN(opened_on), MAX(opened_on), MAX(status_updated_on) FROM fact_tickets")
        ).one()
    lines = ["Tabelas:"]
    for table, rows in columns.groupby("table_name"):
        described = ", ".join(
            f"{c} ({t})" for c, t in zip(rows.column_name, rows.data_type, strict=True)
        )
        lines.append(f"- {table}: {described}")
    lines += [
        f"Grupos de serviço (group_name): {', '.join(sorted(groups.group_name))}",
        f"Situações (status): {', '.join(sorted(statuses.status))}",
        f"Chamados abertos de {period[0]} a {period[1]}; situação conhecida até {period[2]}.",
    ]
    return "\n".join(lines)


@dataclass
class QueryRun:
    sql: str
    result: pd.DataFrame | None = None
    error: str | None = None
    truncated: bool = False

    def as_tool_output(self) -> str:
        if self.error:
            return f"Erro: {self.error}"
        note = f"\n(resultado cortado em {MAX_ROWS} linhas)" if self.truncated else ""
        return self.result.to_csv(index=False) + note


@dataclass
class Answer:
    text: str
    queries: list[QueryRun] = field(default_factory=list)


# Validates the SQL, runs it in a read-only transaction and never raises: errors go back to
# the model as tool output so it can fix the query
def run_readonly_query(engine: Engine, sql: str) -> QueryRun:
    try:
        limited = validate_sql(sql)
    except UnsafeQueryError as error:
        return QueryRun(sql, error=str(error))
    try:
        with engine.connect() as connection:
            cursor = connection.connection.driver_connection
            cursor.execute("SET TRANSACTION READ ONLY")
            result = cursor.execute(limited)
            columns = [column.name for column in result.description]
            frame = pd.DataFrame(result.fetchall(), columns=columns)
            connection.rollback()
    except Exception as error:
        return QueryRun(sql, error=str(error).strip().splitlines()[0])
    return QueryRun(sql, result=frame.head(MAX_ROWS), truncated=len(frame) > MAX_ROWS)


def _text_of(response) -> str:
    return "\n".join(block.text for block in response.content if block.type == "text").strip()


# Tool-use loop: the model may run a few queries (fixing its own errors) before answering
def ask(
    question: str,
    schema: str,
    client: anthropic.Anthropic,
    execute: Callable[[str], QueryRun],
    max_steps: int = MAX_STEPS,
) -> Answer:
    messages = [{"role": "user", "content": question}]
    system = [
        {
            "type": "text",
            "text": f"{INSTRUCTIONS}\n{schema}",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    queries: list[QueryRun] = []
    for _ in range(max_steps):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            tools=[RUN_SQL_TOOL],
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            return Answer("O modelo não respondeu a esta pergunta.", queries)

        tool_uses = [block for block in response.content if block.type == "tool_use"]
        if not tool_uses:
            return Answer(_text_of(response), queries)

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            run = execute(block.input["sql"])
            queries.append(run)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": run.as_tool_output(),
                    "is_error": run.error is not None,
                }
            )
        messages.append({"role": "user", "content": results})
    return Answer(f"Não cheguei a uma resposta em {max_steps} consultas.", queries)
