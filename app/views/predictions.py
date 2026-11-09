import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import fmt_int, fmt_num, fmt_pct, load_model, load_rain, load_tickets
from src.dashboard.labels import place_label, sentence_label
from src.dashboard.style import ACCENT, INK, NEUTRAL, SERIES, ranked_bars, show
from src.dashboard.ui import Stat, callout, header, note, section, stats
from src.ml.features import HORIZON_DAYS, build_features
from src.ml.predict import predict_chance, simulated_features

MODEL = "Gradient boosting"
HISTORY = "Histórico do serviço"
FEATURE_LABELS = {
    "service_name": "Serviço pedido",
    "group_name": "Grupo do serviço",
    "neighborhood_name": "Bairro",
    "rpa": "RPA",
    "month": "Mês",
    "day_of_week": "Dia da semana",
    "is_weekend": "Fim de semana",
    "rain_3d_mm": "Chuva nos últimos 3 dias",
    "service_demand_7d": "Pedidos do serviço na semana",
    "neighborhood_demand_30d": "Pedidos do bairro no mês",
}


@st.cache_data(ttl=3600)
def _features() -> pd.DataFrame:
    return build_features(load_tickets(), load_rain())


artifact = load_model()
if artifact is None:
    st.warning(
        "O modelo ainda não foi treinado. Rode `make train` (o `docker compose up` já treina "
        "depois da carga) e recarregue a página."
    )
    st.stop()

tickets = load_tickets()
results, split = artifact["results"], artifact["split"]
model, history = results[MODEL], results[HISTORY]
reference = artifact["reference_date"]

header(
    "Previsão de atraso",
    f"Na abertura do chamado, o modelo aponta quais vão passar de {HORIZON_DAYS} dias",
    "Um gradient boosting treinado com o histórico estima a chance de cada chamado ser atendido "
    f"em até {HORIZON_DAYS} dias. Ele só usa o que se sabe no momento da abertura: o serviço, o "
    "bairro, a data, a chuva e a demanda dos dias anteriores.",
)
stats(
    [
        Stat(
            fmt_num(model["auc"], 3),
            "AUC no teste",
            f"histórico do serviço: {fmt_num(history['auc'], 3)}",
        ),
        Stat(
            fmt_pct(100 * model["alert_precision"], 0),
            "dos alertas de atraso se confirmam",
            f"histórico do serviço: {fmt_pct(100 * history['alert_precision'], 0)}",
        ),
        Stat(
            fmt_pct(100 * model["alert_recall"], 0),
            "dos atrasos recebem alerta",
            f"histórico do serviço: {fmt_pct(100 * history['alert_recall'], 0)}",
        ),
        Stat(
            fmt_int(artifact["sizes"]["test"]),
            "chamados no teste",
            f"abertos de {split.test_start:%m/%Y} a {split.test_end:%m/%Y}",
        ),
    ]
)

section(
    "Validado em meses que o modelo nunca viu",
    f"Treino com o passado, um intervalo de {HORIZON_DAYS} dias para o desfecho dos últimos "
    "chamados do treino ser conhecido, e teste nos meses seguintes. Depois do teste, os chamados "
    "ainda não têm desfecho: são as previsões de verdade, mostradas mais abaixo.",
)
phases = pd.DataFrame(
    [
        ("Treino", tickets["opened_on"].min(), split.train_end, ACCENT),
        ("Intervalo", split.train_end, split.test_start, NEUTRAL),
        ("Teste", split.test_start, split.test_end, SERIES[1]),
        ("Previsão", split.test_end, reference, SERIES[2]),
    ],
    columns=["phase", "start", "end", "color"],
)
fig = go.Figure()
for row in phases.itertuples():
    fig.add_bar(
        x=[(row.end - row.start).days * 86_400_000],
        base=[row.start],
        y=["fase"],
        orientation="h",
        marker_color=row.color,
        name=row.phase,
        hovertemplate=f"{row.phase}: {row.start:%d/%m/%Y} a {row.end:%d/%m/%Y}<extra></extra>",
    )
for row in phases.itertuples():
    fig.add_annotation(
        x=row.start + (row.end - row.start) / 2,
        y="fase",
        text=row.phase,
        showarrow=False,
        yshift=34,
        font={"color": INK, "size": 12},
    )
fig.update_xaxes(type="date", tickformat="%m/%y", showline=False)
fig.update_yaxes(visible=False)
fig.update_layout(barmode="overlay", showlegend=False, bargap=0.4, margin={"t": 36, "b": 8})
show(fig, height=140)

section(
    "Contra duas alternativas simples, o modelo ganha, com margem pequena no geral",
    "A taxa geral do treino chuta a mesma chance para todos; o histórico do serviço usa a taxa "
    "de atendimento de cada serviço. AUC e precisão: quanto maior, melhor. Brier mede o erro da "
    "chance prevista: quanto menor, melhor.",
)
names = list(results)
columns = st.columns(3, gap="medium")
for column, metric, label, digits in [
    (columns[0], "auc", "AUC", 3),
    (columns[1], "alert_precision", "Precisão do alerta", 2),
    (columns[2], "brier", "Brier (erro)", 3),
]:
    with column:
        st.markdown(f"**{label}**")
        values = [results[name][metric] for name in names]
        fig = ranked_bars(
            names,
            values,
            [fmt_num(value, digits) for value in values],
            highlight={MODEL},
            labels_above=True,
        )
        show(fig, height=190)

left, right = st.columns(2, gap="large")
with left:
    errors = artifact["error_by_group"]
    errors = errors[errors["tickets"] >= 1000].assign(
        group=lambda df: df["group"].map(sentence_label),
        reduction=lambda df: 100 * (1 - df["model_brier"] / df["history_brier"]),
    )
    errors = errors.sort_values("reduction", ascending=False)
    best = errors.head(2)
    section(
        f"O ganho está onde o bairro pesa: o erro cai {best['reduction'].iloc[0]:.0f}% em "
        f"{best['group'].iloc[0].lower()} e {best['reduction'].iloc[1]:.0f}% em "
        f"{best['group'].iloc[1].lower()}",
        "Redução do erro (Brier) do modelo em relação ao histórico do serviço, por grupo, nos "
        "grupos com pelo menos mil chamados no teste.",
    )
    fig = ranked_bars(
        list(errors["group"]),
        list(errors["reduction"].clip(lower=0)),
        [f"{value:.0f}%" for value in errors["reduction"]],
        highlight=set(best["group"]),
    )
    show(fig, height=300)

with right:
    importances = artifact["importances"].rename(FEATURE_LABELS)
    importances = importances[importances >= 0.001]
    section(
        f"{importances.index[0]} é a informação que mais pesa",
        "Quanto a AUC cai quando os valores de cada variável são embaralhados no teste "
        "(importância por permutação). Quanto maior a queda, mais o modelo depende dela.",
    )
    fig = ranked_bars(
        list(importances.index),
        list(importances.values),
        [fmt_num(value, 3) for value in importances.values],
        highlight={importances.index[0]},
    )
    show(fig, height=300)

calibration = artifact["calibration"]
reliable = calibration[calibration["tickets"] >= 500]
gap = 100 * (reliable["observed"] - reliable["predicted"]).abs().max()
left, right = st.columns([2, 3], gap="large")
with left:
    section(
        f"A chance prevista fica a até {gap:.0f} pontos da taxa real de atendimento",
        "Cada ponto junta os chamados do teste com chance prevista parecida. Na diagonal, a "
        "chance prevista é igual à taxa de atendimento real.",
    )
    fig = go.Figure()
    fig.add_scatter(
        x=[0, 1], y=[0, 1], mode="lines", line={"color": NEUTRAL, "width": 1}, hoverinfo="skip"
    )
    fig.add_scatter(
        x=calibration["predicted"],
        y=calibration["observed"],
        mode="lines+markers",
        line={"color": ACCENT, "width": 2},
        marker={"size": 8},
        customdata=calibration["tickets"],
        hovertemplate=(
            "Previsto %{x:.0%}, observado %{y:.0%}<br>%{customdata:,.0f} chamados<extra></extra>"
        ),
    )
    fig.update_xaxes(
        title="Chance prevista", tickformat=".0%", range=[0, 1], dtick=0.25, showgrid=True
    )
    fig.update_yaxes(title="Atendidos em 30 dias", tickformat=".0%", range=[0, 1], dtick=0.25)
    fig.update_layout(showlegend=False)
    show(fig, height=320)

# Tickets opened after the test window have no known outcome yet: these are real forecasts
recent = tickets["is_open"] & (tickets["opened_on"] > split.test_end)
scored = tickets[recent].assign(chance=predict_chance(artifact, _features()[recent]))
alerts = scored[scored["chance"] < 0.5]
with right:
    section(
        f"Na fila de agora, {fmt_int(len(alerts))} chamados recentes têm alerta de atraso",
        f"Chamados abertos depois de {split.test_end:%d/%m/%Y} e ainda sem atendimento, dos "
        f"menos para os mais prováveis de serem atendidos em {HORIZON_DAYS} dias.",
    )
    st.dataframe(
        scored.nsmallest(30, "chance")[["chance", "service", "neighborhood", "opened_on"]],
        hide_index=True,
        height=320,
        column_config={
            "service": st.column_config.TextColumn("Serviço"),
            "neighborhood": st.column_config.TextColumn("Bairro"),
            "opened_on": st.column_config.DateColumn("Aberto em", format="DD/MM/YYYY"),
            "chance": st.column_config.ProgressColumn(
                f"Chance em {HORIZON_DAYS} dias", format="percent", min_value=0, max_value=1
            ),
        },
    )

section(
    "Simule um chamado novo",
    "Escolha o serviço, o bairro, a data e a chuva. A demanda recente vem dos últimos dias dos "
    "dados.",
)
inputs = st.columns(4)
services = sorted(tickets["service_name"].unique())
neighborhoods = sorted(tickets["neighborhood_name"].dropna().unique())
service = inputs[0].selectbox(
    "Serviço",
    services,
    index=services.index("LIMPEZA DE GALERIAS E VALETAS"),
    format_func=sentence_label,
)
neighborhood = inputs[1].selectbox(
    "Bairro", neighborhoods, index=neighborhoods.index("BOA VIAGEM"), format_func=place_label
)
day = inputs[2].date_input("Aberto em", value=reference.date(), format="DD/MM/YYYY")
rain = inputs[3].slider("Chuva nos últimos 3 dias (mm)", 0, 60, 0)

simulated = simulated_features(tickets, service, neighborhood, pd.Timestamp(day), float(rain))
chance = predict_chance(artifact, simulated)[0]
service_rate = artifact["service_rates"].get(service, artifact["global_rate"])
difference = 100 * (chance - service_rate)
stats(
    [
        Stat(fmt_pct(100 * chance, 0), f"de chance de atendimento em {HORIZON_DAYS} dias"),
        Stat(fmt_pct(100 * service_rate, 0), "média histórica do serviço"),
        Stat(
            f"{difference:+.0f} p.p." if abs(difference) >= 0.5 else "0 p.p.",
            "efeito do bairro, da data e da demanda",
        ),
    ]
)
callout(
    "Uso proposto: na triagem, chamados com chance abaixo de 50% vão para uma fila de atenção, "
    "antes de virarem atraso. O alerta acerta mais que a regra pelo histórico do serviço e "
    "aponta onde a região faz diferença."
)
note(
    f"Treinado com {fmt_int(artifact['sizes']['train'])} chamados abertos até "
    f"{split.train_end:%d/%m/%Y}. Detalhes, escolhas e limitações no notebook 04 e em "
    "docs/ml_results.md."
)
