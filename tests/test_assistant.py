from types import SimpleNamespace

import pandas as pd

from src.ai.assistant import QueryRun, ask


def tool_call(sql: str):
    return SimpleNamespace(type="tool_use", id="call-1", input={"sql": sql})


def reply(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


class ScriptedClient:
    # Stands in for the Anthropic client, returning one scripted response per call
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **request):
        self.requests.append(request)
        return self.responses.pop(0)


def test_ask_runs_the_requested_query_and_returns_the_final_answer():
    client = ScriptedClient(
        [
            reply(tool_call("SELECT COUNT(*) AS n FROM v_tickets"), stop_reason="tool_use"),
            reply(SimpleNamespace(type="text", text="Foram 204.408 chamados.")),
        ]
    )
    executed = []

    def execute(sql):
        executed.append(sql)
        return QueryRun(sql, result=pd.DataFrame({"n": [204408]}))

    answer = ask("Quantos chamados?", "schema", client, execute)

    assert answer.text == "Foram 204.408 chamados."
    assert executed == ["SELECT COUNT(*) AS n FROM v_tickets"]
    tool_result = client.requests[1]["messages"][-1]["content"][0]
    assert tool_result["content"].startswith("n\n204408")
    assert tool_result["is_error"] is False


def test_query_errors_go_back_to_the_model_instead_of_raising():
    client = ScriptedClient(
        [
            reply(tool_call("DROP TABLE fact_tickets"), stop_reason="tool_use"),
            reply(SimpleNamespace(type="text", text="Não posso alterar dados.")),
        ]
    )

    answer = ask("Apague tudo", "schema", client, lambda sql: QueryRun(sql, error="bloqueado"))

    assert answer.queries[0].error == "bloqueado"
    assert client.requests[1]["messages"][-1]["content"][0]["is_error"] is True


def test_a_refusal_ends_the_loop_with_a_clear_message():
    client = ScriptedClient([reply(stop_reason="refusal")])

    answer = ask("pergunta", "schema", client, lambda sql: QueryRun(sql))

    assert "não respondeu" in answer.text
