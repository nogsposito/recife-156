import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.data import fmt_int, fmt_pct, load_rain, load_tickets
from src.dashboard.style import SERIES, style
from src.ml.features import HORIZON_DAYS, build_features
from src.ml.predict import load_artifact, predict_chance, simulated_features


@st.cache_resource
def _artifact() -> dict | None:
    return load_artifact()


@st.cache_data(ttl=3600)
def _features() -> pd.DataFrame:
    return build_features(load_tickets(), load_rain())


st.title("Previsões: quais chamados devem passar de 30 dias")
artifact = _artifact()
if artifact is None:
    st.warning(
        "O modelo ainda não foi treinado. Rode `make train` (o `docker compose up` já treina "
        "depois da carga) e recarregue a página."
    )
    st.stop()

tickets = load_tickets()
reference = artifact["reference_date"]
st.caption(
    f"Para quem prioriza a fila: um modelo treinado com o histórico estima, na abertura, a "
    f"chance de cada chamado ser atendido em até {HORIZON_DAYS} dias. Situação em "
    f"{reference:%d/%m/%Y}."
)

# Tickets opened after the test window have no known outcome yet: these are real forecasts
recent = tickets["is_open"] & (tickets["opened_on"] > artifact["split"].test_end)
scored = tickets[recent].assign(chance=predict_chance(artifact, _features()[recent]))
alerts = scored[scored["chance"] < 0.5]

columns = st.columns(3)
columns[0].metric(f"Abertos nos últimos {HORIZON_DAYS} dias e ainda na fila", fmt_int(len(scored)))
columns[1].metric(
    f"Devem passar de {HORIZON_DAYS} dias",
    fmt_int((1 - scored["chance"]).sum()),
    help="Soma das chances de não serem atendidos a tempo: o número esperado de atrasos.",
)
columns[2].metric("Com alerta (chance abaixo de 50%)", fmt_int(len(alerts)))

left, right = st.columns([2, 3])
with left:
    st.subheader("Atrasos esperados por grupo")
    by_group = (
        scored.assign(late=1 - scored["chance"])
        .groupby("group_name")["late"]
        .sum()
        .nlargest(8)
        .sort_values()
        .reset_index()
    )
    fig = px.bar(
        by_group, x="late", y="group_name", orientation="h", color_discrete_sequence=[SERIES[1]]
    )
    fig.update_traces(hovertemplate="%{y}: %{x:.0f} atrasos esperados<extra></extra>")
    fig.update_xaxes(title="Chamados que devem passar de 30 dias")
    fig.update_yaxes(title=None)
    st.plotly_chart(style(fig, height=360))

with right:
    st.subheader("Chamados recentes com menor chance de atendimento a tempo")
    st.dataframe(
        scored.nsmallest(15, "chance")[
            ["service_name", "neighborhood_name", "opened_on", "status", "chance"]
        ],
        hide_index=True,
        height=360,
        column_config={
            "service_name": st.column_config.TextColumn("Serviço"),
            "neighborhood_name": st.column_config.TextColumn("Bairro"),
            "opened_on": st.column_config.DateColumn("Aberto em", format="DD/MM/YYYY"),
            "status": st.column_config.TextColumn("Situação"),
            "chance": st.column_config.ProgressColumn(
                "Chance em 30 dias", format="percent", min_value=0, max_value=1
            ),
        },
    )

st.subheader("Simular um novo chamado")
inputs = st.columns(4)
services = sorted(tickets["service_name"].unique())
neighborhoods = sorted(tickets["neighborhood_name"].dropna().unique())
default_service = services.index("LIMPEZA DE GALERIAS E VALETAS")
service = inputs[0].selectbox("Serviço", services, index=default_service)
neighborhood = inputs[1].selectbox("Bairro", neighborhoods, index=neighborhoods.index("BOA VIAGEM"))
day = inputs[2].date_input("Aberto em", value=reference.date(), format="DD/MM/YYYY")
rain = inputs[3].slider("Chuva nos últimos 3 dias (mm)", 0, 60, 0)

simulated = simulated_features(tickets, service, neighborhood, pd.Timestamp(day), float(rain))
chance = predict_chance(artifact, simulated)[0]
history = artifact["service_rates"].get(service, artifact["global_rate"])
result = st.columns(2)
result[0].metric(f"Chance de ser atendido em até {HORIZON_DAYS} dias", fmt_pct(100 * chance))
result[1].metric(
    "Média histórica do serviço",
    fmt_pct(100 * history),
    delta=f"{100 * (chance - history):+.0f} p.p. pelo bairro, data e demanda",
    delta_color="off",
)

st.subheader("Quão bom é o modelo")
results = pd.DataFrame(artifact["results"]).T.reset_index(names="model")
st.dataframe(
    results[["model", "auc", "brier", "alert_precision", "alert_recall"]],
    hide_index=True,
    column_config={
        "model": st.column_config.TextColumn("Modelo"),
        "auc": st.column_config.NumberColumn("AUC", format="%.3f"),
        "brier": st.column_config.NumberColumn("Brier", format="%.3f"),
        "alert_precision": st.column_config.NumberColumn("Precisão do alerta", format="percent"),
        "alert_recall": st.column_config.NumberColumn("Recall do alerta", format="percent"),
    },
)
split = artifact["split"]
st.caption(
    f"Treinado com chamados abertos até {split.train_end:%d/%m/%Y} e testado nos abertos de "
    f"{split.test_start:%d/%m/%Y} a {split.test_end:%d/%m/%Y}, que o modelo nunca viu. "
    "Detalhes e limitações no notebook 04 e em docs/ml_results.md."
)
