import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import fmt_int, fmt_pct, load_model, load_rain, load_tickets
from src.dashboard.labels import place_label, sentence_label
from src.dashboard.style import ACCENT, BACKGROUND, NEUTRAL, ranked_bars, show
from src.dashboard.ui import Stat, callout, facts, header, note, panel, section
from src.ml.features import HORIZON_DAYS, build_features
from src.ml.predict import predict_chance, simulated_features

MODEL = "Gradient boosting"
HISTORY = "Histórico do serviço"
FEATURE_LABELS = {
    "service_name": "Serviço pedido",
    "group_name": "Grupo do serviço",
    "neighborhood_name": "Bairro",
    "rpa": "Região",
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
    f"Na abertura de cada chamado, o modelo avisa quais pedidos devem passar de {HORIZON_DAYS} "
    "dias sem atendimento, para a central agir antes do atraso.",
    "model_training",
)
facts(
    [
        Stat(
            fmt_pct(100 * model["alert_precision"], 0),
            "dos alertas de atraso se confirmam",
        ),
        Stat(
            fmt_pct(100 * model["alert_recall"], 0),
            "dos chamados que atrasaram tinham recebido alerta",
        ),
        Stat(
            fmt_int(artifact["sizes"]["test"]),
            "chamados usados para medir o acerto",
            f"abertos de {split.test_start:%m/%Y} a {split.test_end:%m/%Y}, fora do treino",
        ),
    ]
)

left, right = st.columns([3, 2], gap="medium")
with left, panel("como-decide"):
    section("Como ele decide")
    st.markdown(
        "O modelo só usa o que já se sabe quando o chamado é aberto: o serviço pedido, o bairro, "
        "a data, a chuva dos últimos três dias e quantos pedidos parecidos chegaram na semana. "
        f"Com isso, estima a chance de o pedido ser atendido em até {HORIZON_DAYS} dias; abaixo "
        "de 50%, o chamado recebe um alerta."
    )
    st.markdown(
        "É um gradient boosting: 300 árvores de decisão pequenas, cada uma corrigindo os "
        "erros das anteriores. Ele foi escolhido porque lida bem com tabelas que misturam "
        "categorias, como serviço e bairro, com números, como chuva e demanda, e porque dá para "
        "medir o que pesa em cada estimativa."
    )
    importances = artifact["importances"].rename(FEATURE_LABELS)
    importances = importances[importances >= 0.001].head(6)
    st.markdown(f"**O que mais pesa: {importances.index[0].lower()}**")
    fig = ranked_bars(
        list(importances.index),
        list(importances.values),
        ["" for _ in importances.values],
        highlight={importances.index[0]},
        hover="%{y}<extra></extra>",
        labels_above=True,
    )
    show(fig, height=40 + 40 * len(importances))

with right, panel("regra-simples"):
    rule = 100 * history["alert_precision"]
    ours = 100 * model["alert_precision"]
    section(
        "Acerta mais que uma regra simples",
        "A regra simples dá a cada chamado a taxa de atendimento do seu serviço. O modelo soma "
        "o bairro, a data, a chuva e a demanda da semana, e por isso erra menos nos alertas.",
    )
    fig = go.Figure(
        go.Bar(
            x=[rule, ours],
            y=["Regra pelo serviço", "Modelo"],
            orientation="h",
            marker_color=[NEUTRAL, ACCENT],
            text=[
                f"{fmt_pct(rule, 0)} dos alertas certos",
                f"{fmt_pct(ours, 0)} dos alertas certos",
            ],
            textposition="inside",
            insidetextanchor="start",
            textfont={"color": BACKGROUND, "size": 13},
            hovertemplate="%{y}: %{x:.0f}%<extra></extra>",
        )
    )
    fig.update_xaxes(visible=False, range=[0, 100])
    fig.update_yaxes(autorange="reversed", showline=False, gridcolor="rgba(0,0,0,0)")
    fig.update_layout(bargap=0.35, margin={"l": 8, "r": 8, "t": 8, "b": 8})
    show(fig, height=170)
    note(
        f"Medido em {fmt_int(artifact['sizes']['test'])} chamados de meses que o modelo não viu "
        "durante o treino."
    )

calibration = artifact["calibration"]
reliable = calibration[calibration["tickets"] >= 500].sort_values("predicted")
gap = 100 * (reliable["observed"] - reliable["predicted"]).abs().max()
with panel("chances"):
    section(
        f"As chances que ele dá batem com o que acontece: a maior diferença é de {gap:.0f} pontos",
        "Os chamados do teste foram agrupados pela chance de atendimento que o modelo deu. Em "
        "cada grupo, a barra verde é a chance prevista e a bege é quantos foram atendidos de "
        f"fato em {HORIZON_DAYS} dias.",
    )
    labels = [f"Disse {value:.0%}".replace(".", ",") for value in reliable["predicted"]]
    fig = go.Figure()
    for column, name, color in [
        ("predicted", "Chance prevista", NEUTRAL),
        ("observed", "Atendidos de fato", ACCENT),
    ]:
        fig.add_bar(
            x=labels,
            y=reliable[column],
            name=name,
            marker_color=color,
            customdata=reliable["tickets"],
            hovertemplate=(f"{name}: " + "%{y:.0%}<br>%{customdata:,.0f} chamados<extra></extra>"),
        )
    fig.update_yaxes(tickformat=".0%", range=[0, 1], dtick=0.25, title="Chamados atendidos")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    show(fig, height=300)

# Tickets opened after the test window have no known outcome yet: these are real forecasts
recent = tickets["is_open"] & (tickets["opened_on"] > split.test_end)
scored = tickets[recent].assign(chance=predict_chance(artifact, _features()[recent]))
alerts = scored[scored["chance"] < 0.5]
with panel("fila-agora"):
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

with panel("simulador"):
    section(
        "Simule um chamado novo",
        "Escolha o serviço, o bairro, a data e a chuva. A demanda recente vem dos últimos dias "
        "dos dados.",
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
    facts(
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
    "antes de virarem atraso."
)
note(
    f"Treinado com {fmt_int(artifact['sizes']['train'])} chamados abertos até "
    f"{split.train_end:%d/%m/%Y}. Validação no tempo, métricas e limitações estão no README e em "
    "docs/ml_results.md."
)
