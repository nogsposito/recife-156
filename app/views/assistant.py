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
from src.dashboard.ui import header, note

SUGGESTIONS = [
    "Quais os 5 bairros com mais chamados de drenagem em aberto?",
    "Quantos chamados foram abertos por mês em 2025?",
    "Onde vejo quanto tempo cada serviço demora?",
    "O que a página Previsão de atraso mostra?",
]
DEFAULT_SQL = (
    "SELECT group_name, COUNT(*) AS tickets\nFROM v_tickets\nGROUP BY group_name\n"
    "ORDER BY tickets DESC"
)
# The demo key has a small spending cap; this keeps one visitor from using it all
QUESTIONS_PER_SESSION = 8
AVATARS = {"user": ":material/person:", "assistant": ":material/forum:"}


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


def show_message(message: dict) -> None:
    with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
        st.markdown(message["content"])
        queries = message.get("queries") or []
        if queries:
            label = "Consulta usada" if len(queries) == 1 else f"{len(queries)} consultas usadas"
            with st.expander(label):
                for run in queries:
                    show_query(run)


# A suggestion click becomes the next question; the pill is cleared so it can be picked again
def _pick_suggestion() -> None:
    st.session_state["pending"] = st.session_state["suggestion"]
    st.session_state["suggestion"] = None


header(
    "Assistente de IA",
    "Converse em português com um agente que consulta os dados do 156 e conhece cada página "
    "deste painel. Ele só lê o banco, e toda resposta mostra a consulta que usou.",
    "forum",
)

chat: list[dict] = st.session_state.setdefault("chat", [])
asked = sum(1 for message in chat if message["role"] == "user")
left = QUESTIONS_PER_SESSION - asked

if not has_credentials():
    st.info(
        "O assistente precisa de uma chave do OpenRouter: coloque `OPENROUTER_API_KEY` no "
        "arquivo `.env` e rode `docker compose up` de novo. Enquanto isso, dá para rodar uma "
        "consulta à mão no fim da página, com as mesmas proteções."
    )
else:
    if not chat:
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            st.markdown(
                "Posso contar quantos chamados há, onde a fila está, quanto cada serviço demora e "
                "explicar onde encontrar cada coisa no painel. Escolha uma sugestão ou escreva "
                "sua pergunta."
            )
    for message in chat:
        show_message(message)

    st.pills(
        "Sugestões",
        SUGGESTIONS,
        key="suggestion",
        on_change=_pick_suggestion,
        label_visibility="collapsed",
    )
    typed = st.chat_input(
        "Pergunte sobre os chamados ou sobre o painel"
        if left > 0
        else "Limite desta visita atingido",
        disabled=left <= 0,
    )
    question = typed or st.session_state.pop("pending", None)

    if question and left > 0:
        history = [{"role": m["role"], "content": m["content"]} for m in chat]
        user_message = {"role": "user", "content": question}
        chat.append(user_message)
        show_message(user_message)
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            with st.spinner("Consultando o banco..."):
                try:
                    answer = ask(
                        question,
                        _schema(),
                        OpenRouterClient(),
                        lambda sql: run_readonly_query(_engine(), sql),
                        history=history,
                    )
                except AssistantError as error:
                    chat.pop()
                    st.error(str(error))
                    st.stop()
        chat.append({"role": "assistant", "content": answer.text, "queries": answer.queries})
        st.rerun()

    columns = st.columns([4, 1], vertical_alignment="center")
    with columns[0]:
        note(
            f"{max(left, 0)} de {QUESTIONS_PER_SESSION} perguntas restantes nesta visita. "
            f"Modelo: {MODEL}, via OpenRouter."
        )
    if chat and columns[1].button("Nova conversa", icon=":material/refresh:"):
        st.session_state["chat"] = []
        st.rerun()

with st.expander("Como o assistente protege o banco"):
    st.markdown(
        f"Toda consulta passa por três barreiras antes de chegar ao banco. A SQL é lida por um "
        f"parser e só passa se for uma única consulta SELECT sobre as tabelas de análise, com no "
        f"máximo {MAX_ROWS} linhas. Ela roda com um usuário que só tem permissão de leitura e não "
        "enxerga as tabelas internas do pipeline. E o banco abre a transação em modo somente "
        "leitura, com no máximo 10 segundos por consulta. O assistente pode entender mal uma "
        "pergunta, por isso a consulta usada fica sempre visível na resposta."
    )

with st.expander("Escrever a SQL à mão", expanded=not has_credentials()):
    sql = st.text_area(
        f"Uma consulta SELECT sobre as tabelas da camada gold, até {MAX_ROWS} linhas",
        value=DEFAULT_SQL,
        height=140,
    )
    if st.button("Executar"):
        show_query(run_readonly_query(_engine(), sql))
