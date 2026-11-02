import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.data import fmt_int, fmt_pct, load_tickets, sidebar_filters
from src.dashboard.style import SERIES, style

all_tickets = load_tickets()
with st.sidebar:
    years = sorted(all_tickets["opened_on"].dt.year.unique())
    year = st.selectbox("Ano de abertura", ["Todos", *years])
tickets = sidebar_filters(all_tickets)
if year != "Todos":
    tickets = tickets[tickets["opened_on"].dt.year == year]
resolved = tickets[~tickets["is_open"]]

st.title("Gerencial: desempenho por serviço")
st.caption(
    "Para a gestão da Emlurb: quanto chega, quanto é atendido e em quanto tempo, por grupo de "
    "serviço e região. Tempos medidos só nos chamados já atendidos."
)

columns = st.columns(4)
columns[0].metric("Chamados no período", fmt_int(len(tickets)))
columns[1].metric("Atendidos", fmt_pct(100 * len(resolved) / max(len(tickets), 1)))
columns[2].metric(
    "Mediana até o atendimento", f"{resolved['days_to_last_update'].median():.0f} dias"
)
columns[3].metric(
    "Atendidos em até 7 dias", fmt_pct(100 * (resolved["days_to_last_update"] <= 7).mean())
)

st.subheader("Indicadores por grupo de serviço")
indicators = (
    tickets.groupby("group_name")
    .agg(tickets=("ticket_id", "size"), open_tickets=("is_open", "sum"))
    .join(
        resolved.groupby("group_name")["days_to_last_update"].agg(
            median_days="median",
            p90_days=lambda days: days.quantile(0.9),
            within_7_days=lambda days: 100 * (days <= 7).mean(),
        )
    )
    .assign(pct_resolved=lambda df: 100 * (1 - df["open_tickets"] / df["tickets"]))
    .sort_values("tickets", ascending=False)
    .reset_index()
)
st.dataframe(
    indicators,
    hide_index=True,
    column_order=[
        "group_name",
        "tickets",
        "pct_resolved",
        "median_days",
        "p90_days",
        "within_7_days",
        "open_tickets",
    ],
    column_config={
        "group_name": st.column_config.TextColumn("Grupo"),
        "tickets": st.column_config.NumberColumn("Chamados", format="localized"),
        "pct_resolved": st.column_config.ProgressColumn(
            "% atendidos", format="%.0f%%", min_value=0, max_value=100
        ),
        "median_days": st.column_config.NumberColumn("Mediana (dias)", format="%.0f"),
        "p90_days": st.column_config.NumberColumn(
            "P90 (dias)", format="%.0f", help="9 em cada 10 atendidos levaram até isso"
        ),
        "within_7_days": st.column_config.NumberColumn("% em até 7 dias", format="%.0f%%"),
        "open_tickets": st.column_config.NumberColumn("Em aberto", format="localized"),
    },
)

left, right = st.columns(2)
with left:
    st.subheader("Abertos e atendidos por mês")
    opened = tickets.groupby(tickets["opened_on"].dt.to_period("M")).size().rename("Abertos")
    closed = resolved.groupby(resolved["status_updated_on"].dt.to_period("M")).size()
    monthly = pd.concat([opened, closed.rename("Atendidos")], axis=1).fillna(0)
    monthly.index = monthly.index.to_timestamp()
    plot_data = monthly.reset_index(names="month").melt(
        id_vars="month", var_name="series", value_name="tickets"
    )
    fig = px.line(plot_data, x="month", y="tickets", color="series", color_discrete_sequence=SERIES)
    fig.update_traces(
        line_width=2, hovertemplate="%{x|%m/%Y}: %{y:,.0f}<extra>%{fullData.name}</extra>"
    )
    fig.update_xaxes(title=None, tickformat="%m/%Y")
    fig.update_yaxes(title="Chamados", rangemode="tozero", tickformat=",")
    st.plotly_chart(style(fig))

with right:
    st.subheader("Mediana de dias até o atendimento por RPA")
    top_groups = indicators["group_name"].head(6)
    by_rpa = (
        resolved[resolved["group_name"].isin(top_groups)]
        .groupby(["group_name", "rpa"])["days_to_last_update"]
        .median()
        .unstack()
        .reindex(top_groups)
    )
    fig = px.imshow(
        by_rpa,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="Blues",
        labels={"x": "RPA", "y": "", "color": "Dias"},
    )
    fig.update_traces(hovertemplate="%{y}, RPA %{x}: %{z:.0f} dias<extra></extra>")
    fig.update_xaxes(
        tickvals=list(by_rpa.columns), ticktext=[f"RPA {int(r)}" for r in by_rpa.columns]
    )
    st.plotly_chart(style(fig))
