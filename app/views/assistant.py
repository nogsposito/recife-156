import anthropic
import streamlit as st

from src.ai.assistant import (
    MAX_ROWS,
    MODEL,
    QueryRun,
    ask,
    describe_schema,
    get_readonly_engine,
    has_credentials,
    run_readonly_query,
)

EXAMPLES = [
    "Quais os 5 bairros com mais chamados de drenagem em aberto?",
    "Qual a mediana de dias até o atendimento de poda de árvores em cada RPA?",
    "Quantos chamados foram abertos por mês em 2025?",
]
DEFAULT_SQL = (
    "SELECT group_name, COUNT(*) AS tickets\nFROM v_tickets\nGROUP BY group_name\n"
    "ORDER BY tickets DESC"
)


@st.cache_resource
def _engine():
    return get_readonly_engine()


@st.cache_data(ttl=3600)
def _schema() -> str:
    return describe_schema(_engine())


def show_query(run: QueryRun) -> None:
    st.code(run.sql, language="sql")
    if run.error:
        st.error(run.error)
        return
    st.dataframe(run.result, hide_index=True)
    if run.truncated:
        st.caption(f"Resultado cortado em {MAX_ROWS} linhas.")


st.title("Pergunte aos dados")
st.caption(
    "Escreva uma pergunta sobre os chamados. O assistente escreve a SQL, consulta o banco com "
    "um usuário que só tem permissão de leitura e responde em português. Toda consulta usada "
    "aparece abaixo da resposta, para conferir."
)

if has_credentials():
    question = st.text_input("Pergunta", placeholder=EXAMPLES[0])
    st.caption("Exemplos: " + "; ".join(EXAMPLES))
    if question:
        with st.spinner("Consultando o banco..."):
            try:
                answer = ask(
                    question,
                    _schema(),
                    anthropic.Anthropic(),
                    lambda sql: run_readonly_query(_engine(), sql),
                )
            except anthropic.RateLimitError:
                st.error("Limite de uso da API atingido. Tente de novo em alguns instantes.")
                st.stop()
            except anthropic.APIStatusError as error:
                st.error(f"A API respondeu com erro {error.status_code}.")
                st.stop()
            except anthropic.APIConnectionError:
                st.error("Não foi possível falar com a API. Verifique a conexão.")
                st.stop()
        st.markdown(answer.text)
        for number, run in enumerate(answer.queries, start=1):
            with st.expander(f"Consulta {number}", expanded=number == len(answer.queries)):
                show_query(run)
        st.caption(f"Modelo: {MODEL}")
else:
    st.info(
        "O assistente precisa de uma chave da API da Anthropic: coloque `ANTHROPIC_API_KEY` "
        "no arquivo `.env` e rode `docker compose up` de novo. Enquanto isso, dá para rodar "
        "uma consulta à mão abaixo, com as mesmas proteções que o assistente usa."
    )

st.subheader("Rodar uma consulta SQL")
sql = st.text_area(
    f"Só uma consulta SELECT, sobre as tabelas da camada gold, até {MAX_ROWS} linhas",
    value=DEFAULT_SQL,
    height=140,
)
if st.button("Executar"):
    show_query(run_readonly_query(_engine(), sql))
