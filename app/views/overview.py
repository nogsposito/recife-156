import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import (
    fmt_int,
    fmt_num,
    fmt_pct,
    load_doc_json,
    load_layer_sizes,
    load_model,
    load_open_points,
    load_pipeline_runs,
    load_quality_checks,
    load_tickets,
)
from src.dashboard.maps import queue_map
from src.dashboard.style import ACCENT, INK, ranked_bars, show
from src.dashboard.ui import Stat, Step, flow, header, note, section, stats

tickets = load_tickets()
reference = tickets["status_updated_on"].max()
resolved = tickets[~tickets["is_open"]]

header(
    "Recife · Central 156 · 2024 e 2025",
    "Onde a manutenção urbana do Recife trava",
    f"Os {fmt_int(len(tickets))} pedidos feitos à central 156 da Emlurb em 2024 e 2025 "
    "mostram o que a cidade mais pede, quanto tempo cada pedido espera e onde a fila se "
    "acumula. Os dados vêm do portal de dados abertos da prefeitura e são cruzados com a "
    "chuva diária.",
)

stats(
    [
        Stat(fmt_int(len(tickets)), "chamados abertos em 2024 e 2025"),
        Stat(fmt_int(tickets["service_name"].nunique()), "tipos de serviço pedidos"),
        Stat(
            fmt_pct(100 * len(resolved) / len(tickets)),
            "já atendidos",
            f"situação em {reference:%d/%m/%Y}",
        ),
        Stat(fmt_int(tickets["is_open"].sum()), "ainda na fila", "o que a central tem a resolver"),
    ]
)

points = load_open_points()
# The title depends on the group picked below it, so it is filled after the choice
title_area = st.container()
groups = ["Todos", *points["group"].value_counts().head(5).index]
chosen = st.pills("Grupo no mapa", groups, default="Todos", label_visibility="collapsed")
shown = points if chosen in (None, "Todos") else points[points["group"] == chosen]
by_rpa = shown["rpa"].value_counts(normalize=True)
first, second = by_rpa.index[:2]
with title_area:
    section(
        f"{fmt_pct(100 * by_rpa.iloc[:2].sum(), 0)} da fila mapeada fica nas RPAs "
        f"{int(first)} e {int(second)}",
        "Cada coluna soma os chamados em aberto num raio de 260 m: quanto mais alta e clara, mais "
        f"pedidos esperando. Entram os {fmt_pct(100 * len(points) / tickets['is_open'].sum(), 0)} "
        "da fila que têm coordenadas. Arraste para girar o mapa.",
    )
queue_map(shown)

section("O que os dados mostram")
columns = st.columns(3, gap="medium")

with columns[0], st.container(border=True):
    top = tickets["service"].value_counts().head(6)
    share = 100 * top / len(tickets)
    leader = top.index[0]
    st.markdown(f"**{leader} é {fmt_pct(share.iloc[0], 0)} de todos os pedidos**")
    fig = ranked_bars(
        list(top.index),
        list(share.values),
        [fmt_pct(value) for value in share.values],
        highlight={leader},
        labels_above=True,
    )
    show(fig, height=260)
    note("Participação dos seis serviços mais pedidos no total de chamados.")
    st.page_link(
        "views/operational.py", label="Ver a fila de hoje", icon=":material/arrow_forward:"
    )

with columns[1], st.container(border=True):
    volume = tickets["group"].value_counts()
    big_groups = volume[volume >= 5000].index
    median_days = (
        resolved[resolved["group"].isin(big_groups)]
        .groupby("group", observed=True)["days_to_last_update"]
        .median()
        .sort_values(ascending=False)
    )
    slowest, fastest = median_days.index[0], median_days.index[-1]
    st.markdown(
        f"**{slowest} leva {median_days.iloc[0]:.0f} dias; "
        f"{fastest.lower()}, {median_days.iloc[-1]:.0f}**"
    )
    fig = ranked_bars(
        list(median_days.index),
        list(median_days.values),
        [f"{value:.0f} dias" for value in median_days.values],
        highlight={slowest},
        labels_above=True,
    )
    show(fig, height=260)
    note("Mediana de dias até o atendimento, nos grupos com mais de 5 mil chamados.")
    st.page_link(
        "views/managerial.py", label="Ver o tempo de atendimento", icon=":material/arrow_forward:"
    )

with columns[2], st.container(border=True):
    opened = tickets.groupby(tickets["opened_on"].dt.to_period("M")).size()
    closed = resolved.groupby(resolved["status_updated_on"].dt.to_period("M")).size()
    backlog = (opened.cumsum() - closed.reindex(opened.index, fill_value=0).cumsum()).rename(
        "backlog"
    )
    backlog.index = backlog.index.to_timestamp()
    monthly_growth = backlog.diff().mean()
    st.markdown(f"**A fila cresce cerca de {fmt_int(monthly_growth)} chamados por mês**")
    fig = go.Figure(
        go.Scatter(
            x=backlog.index,
            y=backlog.values,
            mode="lines",
            line={"color": ACCENT, "width": 2},
            fill="tozeroy",
            fillcolor="rgba(61,155,233,0.14)",
            hovertemplate="%{x|%m/%Y}: %{y:,.0f} em aberto<extra></extra>",
        )
    )
    fig.add_annotation(
        x=backlog.index[-1],
        y=backlog.iloc[-1],
        text=fmt_int(backlog.iloc[-1]),
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        font={"color": INK, "size": 13},
    )
    fig.update_xaxes(tickformat="%m/%y", nticks=6)
    fig.update_yaxes(tickformat=",", rangemode="tozero")
    fig.update_layout(margin={"l": 8, "r": 8, "t": 8, "b": 8})
    show(fig, height=260)
    note("Chamados em aberto no fim de cada mês, contando só os abertos desde janeiro de 2024.")
    st.page_link(
        "views/strategic.py", label="Ver tendência e chuva", icon=":material/arrow_forward:"
    )

runs = load_pipeline_runs()
last_run = (
    runs[runs["status"] == "success"].iloc[0] if (runs["status"] == "success").any() else None
)
checks = load_quality_checks(int(last_run["run_id"])) if last_run is not None else pd.DataFrame()
sizes = load_layer_sizes()

section(
    "Como os dados chegam até aqui",
    "Um pipeline baixa, trata, valida e carrega os dados no banco. Uma nova execução só baixa "
    "o que mudou no portal.",
)
flow(
    [
        Step(
            "1 · FONTES",
            "APIs públicas",
            ["Portal de Dados Abertos do Recife (CKAN)", "Chuva diária do Open-Meteo"],
        ),
        Step(
            "2 · BRONZE",
            "Arquivo bruto versionado",
            ["Parquet por ano, sem alterar nada", "Versão e hash de cada arquivo"],
        ),
        Step(
            "3 · SILVER",
            "Limpeza e validação",
            ["Tipos, textos e coordenadas", f"{len(checks)} checagens de qualidade por carga"],
            f"{fmt_int(last_run['silver_rows'])} chamados" if last_run is not None else "",
        ),
        Step(
            "4 · GOLD",
            "Banco analítico",
            ["PostgreSQL em esquema estrela", "Índices medidos com EXPLAIN ANALYZE"],
            f"{fmt_int(sizes['fact_tickets'])} linhas na tabela fato",
        ),
        Step(
            "5 · USO",
            "Painel, modelos e IA",
            ["Análises e previsão de atraso", "NLP e assistente em SQL"],
        ),
    ]
)
st.page_link(
    "views/pipeline.py",
    label="Ver execuções, checagens e benchmark",
    icon=":material/arrow_forward:",
)

section(
    "O que mais dá para fazer com esses dados",
    "Prever quais chamados vão atrasar, ligar o histórico antigo ao catálogo atual e responder "
    "perguntas em português.",
)
artifact = load_model()
nlp = load_doc_json("nlp_results.json")
columns = st.columns(3, gap="medium")
with columns[0], st.container(border=True):
    st.markdown("**Previsão de atraso**")
    if artifact is not None:
        model = artifact["results"]["Gradient boosting"]
        st.markdown(
            f"Na abertura do chamado, estima a chance de atendimento em 30 dias. "
            f"AUC de {fmt_num(model['auc'], 3)} em meses que o modelo nunca viu; "
            f"{fmt_pct(100 * model['alert_precision'], 0)} dos alertas de atraso se confirmam."
        )
    st.page_link("views/predictions.py", label="Abrir o modelo", icon=":material/arrow_forward:")
with columns[1], st.container(border=True):
    st.markdown("**Histórico com NLP**")
    if nlp is not None:
        best = nlp["original"]["Caracteres (TF-IDF) + regressão logística"]
        st.markdown(
            "As descrições de 2012 a 2023 usam outro catálogo e perderam os acentos. Um "
            "classificador de n-gramas põe no grupo certo "
            f"{fmt_pct(100 * best['ticket_accuracy'], 0)} dos chamados antigos."
        )
    st.page_link("views/history.py", label="Abrir o de-para", icon=":material/arrow_forward:")
with columns[2], st.container(border=True):
    st.markdown("**Pergunte aos dados**")
    st.markdown(
        "Perguntas em português viram SQL, validada e executada com um usuário que só lê. "
        "Toda consulta aparece ao lado da resposta."
    )
    st.page_link("views/assistant.py", label="Fazer uma pergunta", icon=":material/arrow_forward:")
