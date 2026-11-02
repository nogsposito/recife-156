import streamlit as st

st.set_page_config(page_title="Recife 156", layout="wide")

pages = [
    st.Page(
        "views/operational.py", title="Operacional", icon=":material/assignment:", default=True
    ),
    st.Page("views/managerial.py", title="Gerencial", icon=":material/monitoring:"),
    st.Page("views/strategic.py", title="Estratégico", icon=":material/insights:"),
    st.Page("views/predictions.py", title="Previsões", icon=":material/online_prediction:"),
]
page = st.navigation(pages)

with st.sidebar:
    st.caption(
        "Chamados do 156 da Emlurb (Portal de Dados Abertos do Recife) e chuva diária do "
        "Open-Meteo. Os filtros valem para a página aberta."
    )

page.run()
