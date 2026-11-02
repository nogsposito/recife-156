import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.data import (
    AGE_BUCKETS,
    fmt_int,
    fmt_pct,
    load_tickets,
    open_with_age,
    sidebar_filters,
)
from src.dashboard.style import SEQUENTIAL, SERIES, style

all_tickets = load_tickets()
# The open data is a snapshot, so "today" is the most recent status change in it
reference = all_tickets["status_updated_on"].max()
tickets = sidebar_filters(all_tickets)
open_tickets = open_with_age(tickets, reference)
last_30_days = reference - pd.Timedelta(days=30)

st.title("Operacional: a fila de atendimento")
st.caption(
    "Para quem coordena a central e as equipes de campo: o que chegou nos últimos dias e o que "
    f"está parado. Situação em {reference:%d/%m/%Y}, data mais recente dos dados abertos."
)

old_share = 100 * (open_tickets["age_days"] > 180).mean() if len(open_tickets) else 0
columns = st.columns(4)
columns[0].metric(
    "Abertos nos últimos 30 dias", fmt_int((tickets["opened_on"] > last_30_days).sum())
)
columns[1].metric(
    "Atendidos nos últimos 30 dias",
    fmt_int(((~tickets["is_open"]) & (tickets["status_updated_on"] > last_30_days)).sum()),
)
columns[2].metric("Fila em aberto", fmt_int(len(open_tickets)))
columns[3].metric(
    "Fila parada há mais de 180 dias",
    fmt_pct(old_share),
    help="Parte dos chamados em aberto que foram abertos há mais de 180 dias.",
)

st.subheader("Chamados abertos por dia nos últimos 90 dias")
recent = (
    tickets[tickets["opened_on"] > reference - pd.Timedelta(days=90)]
    .groupby("opened_on")
    .size()
    .rename("tickets")
    .reset_index()
)
fig = px.bar(recent, x="opened_on", y="tickets", color_discrete_sequence=[SERIES[0]])
fig.update_traces(hovertemplate="%{x|%d/%m/%Y}: %{y} chamados<extra></extra>")
fig.update_xaxes(title=None, tickformat="%d/%m")
fig.update_yaxes(title="Chamados")
st.plotly_chart(style(fig, height=300))

left, right = st.columns(2)
with left:
    st.subheader("Bairros com mais chamados em aberto")
    by_neighborhood = (
        open_tickets.groupby(["neighborhood_name", "age_bucket"], observed=False)
        .size()
        .unstack(fill_value=0)
    )
    top = by_neighborhood.sum(axis=1).nlargest(15).index
    plot_data = (
        by_neighborhood.loc[top]
        .reset_index()
        .melt(id_vars="neighborhood_name", var_name="age_bucket", value_name="tickets")
    )
    fig = px.bar(
        plot_data,
        x="tickets",
        y="neighborhood_name",
        color="age_bucket",
        orientation="h",
        category_orders={"age_bucket": AGE_BUCKETS, "neighborhood_name": list(top)},
        color_discrete_sequence=SEQUENTIAL,
    )
    fig.update_traces(hovertemplate="%{y}: %{x} chamados<extra>%{fullData.name}</extra>")
    fig.update_layout(bargap=0.25)
    fig.update_xaxes(title="Chamados em aberto", tickformat=",")
    fig.update_yaxes(title=None)
    # Room above the plot for the legend, so it never covers the first bar
    st.plotly_chart(style(fig, height=480).update_layout(margin_t=60))

with right:
    st.subheader("Serviços com mais pendências")
    by_service = (
        open_tickets.groupby("service_name")
        .agg(
            open_tickets=("age_days", "size"),
            median_age=("age_days", "median"),
            over_180=("age_days", lambda age: 100 * (age > 180).mean()),
        )
        .nlargest(15, "open_tickets")
        .reset_index()
    )
    st.dataframe(
        by_service,
        hide_index=True,
        height=480,
        column_config={
            "service_name": st.column_config.TextColumn("Serviço", width="medium"),
            "open_tickets": st.column_config.NumberColumn(
                "Em aberto", format="localized", width="small"
            ),
            "median_age": st.column_config.NumberColumn(
                "Idade (dias)", format="%d", width="small", help="Idade mediana da fila"
            ),
            "over_180": st.column_config.NumberColumn("> 180 dias", format="%.0f%%", width="small"),
        },
    )
