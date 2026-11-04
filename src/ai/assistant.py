import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd
import requests
from sqlalchemy import Engine, create_engine, text

from src.ai.sql_guard import ALLOWED_TABLES, MAX_ROWS, UnsafeQueryError, validate_sql
from src.config import with_psycopg

MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-5.5")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ASSISTANT_DATABASE_URL = with_psycopg(
    os.getenv(
        "ASSISTANT_DATABASE_URL",
        "postgresql+psycopg://assistant_readonly:assistant@localhost:5433/recife156",
    )
)
MAX_STEPS = 5
MAX_TOKENS = 2000

RUN_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": (
            "Executa uma única consulta SELECT no PostgreSQL dos chamados do 156, com usuário "
            f"somente leitura, e devolve até {MAX_ROWS} linhas em CSV. Use para qualquer número "
            "que a resposta precise."
        ),
        "parameters": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "Uma consulta SELECT"}},
            "required": ["sql"],
            "additionalProperties": False,
        },
    },
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


class AssistantError(Exception):
    """Failure talking to the model, with a message that is safe to show on screen."""


class ChatClient(Protocol):
    def complete(self, **request) -> dict: ...


def has_credentials() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


# OpenRouter speaks the OpenAI chat completions format. The key stays on the server: the
# browser only sees the answer, never the request
class OpenRouterClient:
    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ["OPENROUTER_API_KEY"]

    def complete(self, **request) -> dict:
        try:
            response = requests.post(
                OPENROUTER_URL,
                json=request,
                headers={"Authorization": f"Bearer {self._api_key}", "X-Title": "Recife 156"},
                timeout=(10, 120),
            )
        except requests.RequestException as error:
            raise AssistantError("Não foi possível falar com a API do modelo.") from error
        if response.status_code == 402:
            raise AssistantError("O crédito de demonstração do assistente acabou.")
        if response.status_code == 429:
            raise AssistantError("Muitas perguntas ao mesmo tempo. Tente de novo em instantes.")
        if response.status_code in (401, 403):
            raise AssistantError("A chave da API do modelo não foi aceita.")
        if not response.ok:
            raise AssistantError(f"A API do modelo respondeu com erro {response.status_code}.")
        body = response.json()
        if "choices" not in body:
            raise AssistantError("A API do modelo devolveu uma resposta sem conteúdo.")
        return body


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


def _run_tool_call(call: dict, execute: Callable[[str], QueryRun]) -> QueryRun:
    try:
        sql = json.loads(call["function"]["arguments"])["sql"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return QueryRun("", error="Chamada sem uma consulta SQL válida no campo sql.")
    return execute(sql)


# Tool-use loop: the model may run a few queries (fixing its own errors) before answering
def ask(
    question: str,
    schema: str,
    client: ChatClient,
    execute: Callable[[str], QueryRun],
    max_steps: int = MAX_STEPS,
) -> Answer:
    messages = [
        {"role": "system", "content": f"{INSTRUCTIONS}\n{schema}"},
        {"role": "user", "content": question},
    ]
    queries: list[QueryRun] = []
    for _ in range(max_steps):
        response = client.complete(
            model=MODEL, messages=messages, tools=[RUN_SQL_TOOL], max_tokens=MAX_TOKENS
        )
        choice = response["choices"][0]
        message = choice["message"]
        if choice.get("finish_reason") == "content_filter" or message.get("refusal"):
            return Answer("O modelo não respondeu a esta pergunta.", queries)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            text = (message.get("content") or "").strip()
            return Answer(text or "O modelo não respondeu a esta pergunta.", queries)

        messages.append(
            {"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls}
        )
        for call in tool_calls:
            run = _run_tool_call(call, execute)
            queries.append(run)
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": run.as_tool_output()}
            )
    return Answer(f"Não cheguei a uma resposta em {max_steps} consultas.", queries)
