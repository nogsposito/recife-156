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
from src.dashboard.labels import rpa_label
from src.dashboard.maps import queue_map
from src.dashboard.neighborhoods import (
    describe,
    load_boundaries,
    neighborhood_map,
    neighborhood_stats,
)
from src.dashboard.style import ACCENT, INK, ranked_bars, show
from src.dashboard.ui import (
    Stage,
    Stat,
    facts,
    glossary,
    group,
    header,
    note,
    panel,
    panel_title,
    pipeline_flow,
    statement,
)

MAP_HEIGHT = 640

tickets = load_tickets()
reference = tickets["status_updated_on"].max()
resolved = tickets[~tickets["is_open"]]

header(
    "Visão geral",
    "O que o Recife pede à central 156, quanto cada pedido espera e onde a fila se acumula.",
    "home",
)
statement(
    f"Em 2024 e 2025, a central 156 da Emlurb recebeu [[{fmt_int(len(tickets))}]] pedidos de "
    f"manutenção urbana, de [[{fmt_int(tickets['service_name'].nunique())}]] tipos de serviço. "
    f"[[{fmt_pct(100 * len(resolved) / len(tickets))}]] já foram atendidos, e "
    f"[[{fmt_int(tickets['is_open'].sum())}]] seguiam na fila em {reference:%d/%m/%Y}."
)

group("O que cada termo quer dizer")
glossary(
    [
        (
            "156",
            "Canal de atendimento da Prefeitura do Recife, por onde os moradores pedem serviços "
            "na rua.",
        ),
        (
            "Emlurb",
            "Empresa de Manutenção e Limpeza Urbana do Recife. É quem executa os pedidos: "
            "iluminação, limpeza, poda de árvores, drenagem e pavimentação.",
        ),
        (
            "Chamado",
            "Cada pedido registrado no 156. Fica em aberto até a Emlurb marcar como atendido.",
        ),
        (
            "Fila",
            f"Os chamados ainda em aberto em {reference:%d/%m/%Y}, a data mais recente dos dados "
            "abertos.",
        ),
        (
            "RPA",
            "Região Político-Administrativa. A prefeitura agrupa os 94 bairros em 6 regiões: "
            "Centro, Norte, Noroeste, Oeste, Sudoeste e Sul.",
        ),
    ]
)

# The title depends on the choices made below it, so it is filled after them
title_area = st.container()
controls = st.columns([4, 1.3], vertical_alignment="center")
open_groups = tickets.loc[tickets["is_open"], "group"].value_counts().head(5).index
chosen = controls[0].pills(
    "Grupo no mapa", ["Todos", *open_groups], default="Todos", label_visibility="collapsed"
)
view = controls[1].segmented_control(
    "Visualização", ["Bairros", "Colunas 3D"], default="Bairros", label_visibility="collapsed"
)
all_groups = chosen in (None, "Todos")
filtered = tickets if all_groups else tickets[tickets["group"] == chosen]

if view == "Colunas 3D":
    points = load_open_points()
    shown = points if all_groups else points[points["group"] == chosen]
    by_rpa = shown["rpa"].value_counts(normalize=True)
    first, second = by_rpa.index[:2]
    with title_area:
        group(
            f"{fmt_pct(100 * by_rpa.iloc[:2].sum(), 0)} da fila mapeada fica nas regiões "
            f"{rpa_label(first)} e {rpa_label(second)}",
            "Cada coluna soma os chamados em aberto num raio de 260 m: quanto mais alta e clara, "
            f"mais pedidos esperando. Entram os "
            f"{fmt_pct(100 * len(points) / tickets['is_open'].sum(), 0)} da fila que têm "
            "coordenadas. Arraste para girar o mapa.",
        )
    queue_map(shown, height=MAP_HEIGHT)
else:
    boundaries = load_boundaries()
    places = {f["properties"]["name"]: f["properties"] for f in boundaries["features"]}
    by_neighborhood = neighborhood_stats(filtered, reference, "group" if all_groups else "service")
    leader = by_neighborhood["open_tickets"].idxmax()
    with title_area:
        group(
            f"Entre todos os bairros, {places[leader]['label']} tem a maior fila: "
            f"{fmt_int(by_neighborhood.loc[leader, 'open_tickets'])} chamados em aberto",
            "Quanto mais vermelho o bairro, mais chamados esperando. Clique num bairro para ver o "
            "resumo ao lado. Bairros maiores costumam ter filas maiores; o resumo compara a "
            "espera com a da cidade nos mesmos serviços.",
        )
    open_filtered = filtered[filtered["is_open"]]
    city_over_180 = ((reference - open_filtered["opened_on"]).dt.days > 180).mean()
    map_column, panel_column = st.columns([3, 2], gap="medium")
    with map_column:
        selected = neighborhood_map(
            boundaries, by_neighborhood, city_over_180, default=leader, height=MAP_HEIGHT
        )
    with panel_column, panel("bairro", height=MAP_HEIGHT):
        place = places.get(selected, {"label": selected, "rpa": 0})
        rpa = place["rpa"]
        panel_title(f"Região {rpa_label(rpa)}" if rpa else "", place["label"])
        if selected in by_neighborhood.index:
            row = by_neighborhood.loc[selected]
            facts(
                [
                    Stat(fmt_int(row["open_tickets"]), "chamados em aberto"),
                    Stat(fmt_pct(100 * row["over_180"], 0), "há mais de seis meses"),
                ]
            )
            st.markdown(describe(row, city_over_180))
            by = "group" if all_groups else "service"
            mix = open_filtered.loc[open_filtered["neighborhood_name"] == selected, by]
            mix = mix.value_counts(normalize=True).head(4)
            fig = ranked_bars(
                list(mix.index),
                list(100 * mix.values),
                [fmt_pct(100 * value, 0) for value in mix.values],
                highlight={mix.index[0]},
                labels_above=True,
            )
            show(fig, height=40 + 44 * len(mix))
        else:
            st.markdown("Nenhum chamado em aberto neste bairro com esse filtro.")

group("O que os dados mostram")
columns = st.columns(3, gap="medium")

with columns[0], panel("servicos"):
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

with columns[1], panel("tempo"):
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

with columns[2], panel("fila"):
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
            fillcolor="rgba(190,165,125,0.14)",
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

group(
    "Como os dados chegam até aqui",
    "Um pipeline baixa, trata, valida e carrega os dados no banco. Uma nova execução só baixa "
    "o que mudou no portal.",
)
pipeline_flow(
    [
        Stage(
            "Fontes",
            "APIs públicas",
            chips=["Portal de Dados Abertos do Recife", "Chuva diária do Open-Meteo"],
        ),
        Stage("Bronze", "Arquivo bruto", "Parquet por ano, guardado como veio, com versão."),
        Stage(
            "Silver",
            "Limpeza e validação",
            "Tipos, textos e coordenadas conferidos.",
            f"{fmt_int(last_run['silver_rows'])} chamados" if last_run is not None else "",
        ),
        Stage(
            "Gold",
            "Banco analítico",
            "PostgreSQL em esquema estrela.",
            f"{fmt_int(sizes['fact_tickets'])} linhas na tabela fato",
        ),
        Stage("Uso", "Este painel", chips=["Análises", "Previsão de atraso", "Assistente de IA"]),
    ],
    ["só o que mudou", "versão e hash", f"{len(checks)} checagens", "carga completa"],
)
st.page_link(
    "views/pipeline.py",
    label="Ver execuções, checagens e benchmark",
    icon=":material/arrow_forward:",
)

group(
    "O que mais dá para fazer com esses dados",
    "Prever quais chamados vão atrasar, ligar o histórico antigo ao catálogo atual e responder "
    "perguntas em português.",
)
artifact = load_model()
nlp = load_doc_json("nlp_results.json")
columns = st.columns(3, gap="medium")
with columns[0], panel("modelo"):
    st.markdown("**Previsão de atraso**")
    if artifact is not None:
        model = artifact["results"]["Gradient boosting"]
        st.markdown(
            "Na abertura do chamado, avisa quais pedidos devem passar de 30 dias. De cada 10 "
            f"alertas, {fmt_num(10 * model['alert_precision'], 0)} se confirmam em meses que o "
            "modelo nunca viu."
        )
    st.page_link("views/predictions.py", label="Abrir o modelo", icon=":material/arrow_forward:")
with columns[1], panel("nlp"):
    st.markdown("**Histórico com NLP**")
    if nlp is not None:
        best = nlp["original"]["Caracteres (TF-IDF) + regressão logística"]
        st.markdown(
            "As descrições de 2012 a 2023 usam outro catálogo e perderam os acentos. Um "
            "classificador de texto põe no grupo certo "
            f"{fmt_pct(100 * best['ticket_accuracy'], 0)} dos chamados antigos."
        )
    st.page_link("views/history.py", label="Abrir o de-para", icon=":material/arrow_forward:")
with columns[2], panel("agente"):
    st.markdown("**Assistente de IA**")
    st.markdown(
        "Responde em português sobre os dados e sobre o painel. Só lê o banco, e toda consulta "
        "que ele faz aparece ao lado da resposta."
    )
    st.page_link("views/assistant.py", label="Fazer uma pergunta", icon=":material/arrow_forward:")
