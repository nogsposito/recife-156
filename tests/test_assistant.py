import json

import pandas as pd

from src.ai.assistant import QueryRun, ask


def tool_call(sql: str, call_id: str = "call-1") -> dict:
    arguments = json.dumps({"sql": sql})
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "run_sql", "arguments": arguments},
    }


def reply(content: str | None = None, tool_calls=None, finish_reason: str = "stop") -> dict:
    message = {"role": "assistant", "content": content, "tool_calls": tool_calls}
    return {"choices": [{"message": message, "finish_reason": finish_reason}]}


class ScriptedClient:
    # Stands in for the OpenRouter client, returning one scripted response per call
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def complete(self, **request):
        self.requests.append(json.loads(json.dumps(request)))
        return self.responses.pop(0)


def test_ask_runs_the_requested_query_and_returns_the_final_answer():
    client = ScriptedClient(
        [
            reply(tool_calls=[tool_call("SELECT COUNT(*) AS n FROM v_tickets")]),
            reply("Foram 204.408 chamados."),
        ]
    )
    executed = []

    def execute(sql):
        executed.append(sql)
        return QueryRun(sql, result=pd.DataFrame({"n": [204408]}))

    answer = ask("Quantos chamados?", "schema", client, execute)

    assert answer.text == "Foram 204.408 chamados."
    assert executed == ["SELECT COUNT(*) AS n FROM v_tickets"]
    tool_message = client.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool" and tool_message["tool_call_id"] == "call-1"
    assert tool_message["content"].startswith("n\n204408")


def test_query_errors_go_back_to_the_model_instead_of_raising():
    client = ScriptedClient(
        [
            reply(tool_calls=[tool_call("DROP TABLE fact_tickets")]),
            reply("Não posso alterar dados."),
        ]
    )

    answer = ask("Apague tudo", "schema", client, lambda sql: QueryRun(sql, error="bloqueado"))

    assert answer.queries[0].error == "bloqueado"
    assert client.requests[1]["messages"][-1]["content"] == "Erro: bloqueado"


def test_malformed_tool_arguments_become_an_error_for_the_model():
    broken = {"id": "call-1", "type": "function", "function": {"name": "run_sql", "arguments": "{"}}
    client = ScriptedClient([reply(tool_calls=[broken]), reply("Desculpe.")])

    answer = ask("pergunta", "schema", client, lambda sql: QueryRun(sql))

    assert "SQL válida" in answer.queries[0].error


def test_a_refusal_ends_the_loop_with_a_clear_message():
    client = ScriptedClient([reply(finish_reason="content_filter")])

    answer = ask("pergunta", "schema", client, lambda sql: QueryRun(sql))

    assert "não respondeu" in answer.text
