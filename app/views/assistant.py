import streamlit as st

from src.ai.assistant import (
    MAX_ROWS,
    MODEL,
    AssistantError,
    OpenRouterClient,
    QueryRun,
    ask,
    describe_schema,
    get_readonly_engine,
    has_credentials,
    run_readonly_query,
)
from src.dashboard.ui import Step, flow, header, note, section

EXAMPLES = [
    "Quais os 5 bairros com mais chamados de drenagem em aberto?",
    "Qual a mediana de dias até o atendimento de poda de árvores em cada RPA?",
    "Quantos chamados foram abertos por mês em 2025?",
]
DEFAULT_SQL = (
    "SELECT group_name, COUNT(*) AS tickets\nFROM v_tickets\nGROUP BY group_name\n"
    "ORDER BY tickets DESC"
)
# The demo key has a small spending cap; this keeps one visitor from using it all
QUESTIONS_PER_SESSION = 8


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


header(
    "Consulta aos dados",
    "Pergunte aos dados em português",
    "Um modelo de linguagem lê a pergunta, escreve a consulta SQL, vê o resultado e responde. "
    "Ele pode errar a SQL e corrigir sozinho, mas não consegue alterar nada: toda consulta passa "
    "por três barreiras antes de chegar ao banco, e aparece abaixo da resposta para conferir.",
)
flow(
    [
        Step(
            "1", "Validação da SQL", ["Uma única consulta SELECT", "Só as tabelas da camada gold"]
        ),
        Step(
            "2", "Usuário somente leitura", ["Sem permissão de escrita", "Sem acesso ao schema ops"]
        ),
        Step(
            "3",
            "Limites no banco",
            ["Transação READ ONLY", f"10 s por consulta, {MAX_ROWS} linhas"],
        ),
    ]
)

asked = st.session_state.setdefault("questions_asked", 0)
if has_credentials():
    section("Faça uma pergunta")
    chosen = st.pills("Exemplos", EXAMPLES, label_visibility="collapsed")
    with st.form("question", border=False):
        question = st.text_input(
            "Pergunta", value=chosen or "", placeholder=EXAMPLES[0], label_visibility="collapsed"
        )
        submitted = st.form_submit_button("Perguntar", type="primary")
    if submitted and question.strip():
        if asked >= QUESTIONS_PER_SESSION:
            st.warning(
                f"Esta demonstração aceita {QUESTIONS_PER_SESSION} perguntas por visita. "
                "A consulta SQL manual abaixo continua disponível."
            )
        else:
            st.session_state["questions_asked"] = asked + 1
            with st.spinner("Consultando o banco..."):
                try:
                    answer = ask(
                        question,
                        _schema(),
                        OpenRouterClient(),
                        lambda sql: run_readonly_query(_engine(), sql),
                    )
                except AssistantError as error:
                    st.error(str(error))
                    st.stop()
            with st.container(border=True):
                st.markdown(answer.text)
            for number, run in enumerate(answer.queries, start=1):
                with st.expander(f"Consulta {number}", expanded=number == len(answer.queries)):
                    show_query(run)
    note(
        f"Modelo: {MODEL}, via OpenRouter. "
        f"{QUESTIONS_PER_SESSION - st.session_state['questions_asked']} perguntas restantes "
        "nesta visita."
    )
else:
    st.info(
        "O assistente precisa de uma chave do OpenRouter: coloque `OPENROUTER_API_KEY` no "
        "arquivo `.env` e rode `docker compose up` de novo. Enquanto isso, dá para rodar uma "
        "consulta à mão abaixo, com as mesmas proteções."
    )

with st.expander("Escrever a SQL à mão", expanded=not has_credentials()):
    sql = st.text_area(
        f"Uma consulta SELECT sobre as tabelas da camada gold, até {MAX_ROWS} linhas",
        value=DEFAULT_SQL,
        height=140,
    )
    if st.button("Executar"):
        show_query(run_readonly_query(_engine(), sql))
