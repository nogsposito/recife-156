import sys
from pathlib import Path

import streamlit as st

# Streamlit Community Cloud runs the app without installing the project, so `src` has to be
# importable from the repository root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.ui import apply_theme  # noqa: E402

st.set_page_config(page_title="Recife 156", page_icon=":material/location_city:", layout="wide")
apply_theme()

assistant = st.Page("views/assistant.py", title="Assistente de IA", icon=":material/forum:")
pages = {
    "Projeto": [
        st.Page("views/overview.py", title="Visão geral", icon=":material/home:", default=True),
    ],
    "Análises": [
        st.Page("views/operational.py", title="A fila hoje", icon=":material/assignment:"),
        st.Page("views/managerial.py", title="Tempo de atendimento", icon=":material/timer:"),
        st.Page("views/strategic.py", title="Tendência e chuva", icon=":material/rainy:"),
    ],
    "Modelos e IA": [
        st.Page(
            "views/predictions.py", title="Previsão de atraso", icon=":material/model_training:"
        ),
        st.Page("views/history.py", title="Histórico com NLP", icon=":material/translate:"),
        assistant,
    ],
    "Engenharia": [
        st.Page("views/pipeline.py", title="Pipeline e qualidade", icon=":material/database:"),
    ],
}
page = st.navigation(pages)

with st.sidebar:
    st.caption(
        "Dados: chamados do 156 da Emlurb, do Portal de Dados Abertos do Recife, e chuva diária "
        "do Open-Meteo. RPA é uma das 6 regiões em que a prefeitura divide os bairros. Os "
        "filtros valem só para a página aberta."
    )

# The assistant is one click away from every page, in the corner of the screen
if page.url_path != assistant.url_path:
    with st.container(key="agent-fab"):
        st.page_link(assistant, label="Pergunte ao assistente", icon=":material/forum:")

page.run()
