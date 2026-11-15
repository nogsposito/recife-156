import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import (
    AGE_BUCKETS,
    fmt_int,
    fmt_num,
    fmt_pct,
    load_tickets,
    open_with_age,
    sidebar_filters,
)
from src.dashboard.style import ACCENT, BACKGROUND, NEUTRAL, SEQUENTIAL, show
from src.dashboard.ui import Stat, facts, header, note, panel, section

all_tickets = load_tickets()
# The open data is a snapshot, so "today" is the most recent status change in it
reference = all_tickets["status_updated_on"].max()
tickets = sidebar_filters(all_tickets)
open_tickets = open_with_age(tickets, reference)
last_30_days = reference - pd.Timedelta(days=30)

old_share = 100 * (open_tickets["age_days"] > 180).mean() if len(open_tickets) else 0
header(
    "A fila hoje",
    "O que chegou nos últimos dias e onde os pedidos estão parados, para quem coordena a central "
    f"e as equipes de campo. Situação em {reference:%d/%m/%Y}.",
    "assignment",
)

opened_30 = (tickets["opened_on"] > last_30_days).sum()
closed_30 = ((~tickets["is_open"]) & (tickets["status_updated_on"] > last_30_days)).sum()
balance = closed_30 - opened_30
facts(
    [
        Stat(
            fmt_int(len(open_tickets)),
            "chamados esperando atendimento",
            f"{fmt_pct(old_share, 0)} há mais de seis meses",
        ),
        Stat(fmt_int(opened_30), "abertos nos últimos 30 dias"),
        Stat(
            fmt_int(closed_30),
            "atendidos nos últimos 30 dias",
            "a fila diminuiu" if balance > 0 else "a fila cresceu",
        ),
        Stat(
            f"{open_tickets['age_days'].median():.0f} dias" if len(open_tickets) else "-",
            "idade mediana da fila",
        ),
    ]
)

if tickets.empty:
    st.info("Nenhum chamado com esses filtros.")
    st.stop()

recent = (
    tickets[tickets["opened_on"] > reference - pd.Timedelta(days=90)]
    .groupby("opened_on")
    .size()
    .rename("tickets")
    .reset_index()
)
recent["weekend"] = recent["opened_on"].dt.day_of_week >= 5
weekday_mean = recent.loc[~recent["weekend"], "tickets"].mean()
weekend_mean = recent.loc[recent["weekend"], "tickets"].mean()
with panel("ritmo"):
    section(
        f"Dias úteis recebem {fmt_num(weekday_mean / max(weekend_mean, 1))} vezes mais chamados "
        "que o fim de semana",
        f"Chamados abertos por dia nos últimos 90 dias: média de {weekday_mean:.0f} por dia útil "
        f"e {weekend_mean:.0f} por dia de fim de semana. A escala das equipes pode seguir esse "
        "ritmo.",
    )
    fig = go.Figure()
    for is_weekend, name, color in [
        (False, "Dia útil", ACCENT),
        (True, "Fim de semana", NEUTRAL),
    ]:
        part = recent[recent["weekend"] == is_weekend]
        fig.add_bar(
            x=part["opened_on"],
            y=part["tickets"],
            name=name,
            marker_color=color,
            hovertemplate="%{x|%a %d/%m}: %{y} chamados<extra></extra>",
        )
    fig.update_xaxes(tickformat="%d/%m")
    fig.update_yaxes(title="Chamados por dia")
    fig.update_layout(bargap=0.15)
    show(fig, height=280)

left, right = st.columns(2, gap="medium")
with left, panel("bairros"):
    by_neighborhood = (
        open_tickets.groupby(["neighborhood", "age_bucket"], observed=False)
        .size()
        .unstack(fill_value=0)
    )
    top = by_neighborhood.sum(axis=1).nlargest(12)
    section(
        f"Entre todos os bairros, {top.index[0]} tem a maior fila: {fmt_int(top.iloc[0])} chamados",
        "Os 12 bairros com mais chamados em aberto, pela idade do pedido. Bairro grande costuma "
        "ter fila grande, então a barra mede volume de trabalho; para comparar a espera entre "
        "bairros, use o mapa da visão geral.",
    )
    plot_data = (
        by_neighborhood.loc[top.index]
        .reset_index()
        .melt(id_vars="neighborhood", var_name="age_bucket", value_name="tickets")
    )
    fig = px.bar(
        plot_data,
        x="tickets",
        y="neighborhood",
        color="age_bucket",
        orientation="h",
        category_orders={"age_bucket": AGE_BUCKETS, "neighborhood": list(top.index)},
        color_discrete_sequence=SEQUENTIAL,
    )
    fig.update_traces(
        hovertemplate="%{y}: %{x} chamados<extra>%{fullData.name}</extra>",
        marker_line_color=BACKGROUND,
        marker_line_width=1,
    )
    fig.update_xaxes(title="Chamados em aberto", tickformat=",", showgrid=True)
    fig.update_yaxes(title=None, showline=False)
    fig.update_layout(bargap=0.25, legend_title_text=None)
    show(fig, height=440)

with right, panel("servicos"):
    by_service = (
        open_tickets.groupby("service", observed=True)
        .agg(
            open_tickets=("age_days", "size"),
            median_age=("age_days", "median"),
            over_180=("age_days", lambda age: (age > 180).mean()),
        )
        .nlargest(12, "open_tickets")
        .reset_index()
    )
    first = by_service.iloc[0]
    section(
        f"{first['service']} concentra "
        f"{fmt_pct(100 * first['open_tickets'] / len(open_tickets), 0)} da fila",
        "Serviços com mais chamados em aberto. A última coluna mostra quanto de cada fila já "
        "passou de seis meses.",
    )
    st.dataframe(
        by_service,
        hide_index=True,
        height=440,
        column_config={
            "service": st.column_config.TextColumn("Serviço", width="medium"),
            "open_tickets": st.column_config.NumberColumn("Em aberto", format="localized"),
            "median_age": st.column_config.NumberColumn(
                "Idade mediana", format="%d dias", help="Metade da fila é mais antiga que isso"
            ),
            "over_180": st.column_config.ProgressColumn(
                "Mais de 180 dias", format="percent", min_value=0, max_value=1
            ),
        },
    )
note(
    "Tempo de espera conta da abertura até a data de referência. Chamados resolvidos sem baixa no "
    "sistema aparecem como abertos, então parte da fila antiga pode ser falha de registro."
)
