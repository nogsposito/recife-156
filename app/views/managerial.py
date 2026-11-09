import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import fmt_int, fmt_pct, load_tickets, sidebar_filters
from src.dashboard.style import ACCENT, BLUE_SCALE, GRID, NEUTRAL, SERIES, ranked_bars, show
from src.dashboard.ui import Stat, header, note, section, stats

all_tickets = load_tickets()
with st.sidebar:
    years = sorted(all_tickets["opened_on"].dt.year.unique())
    year = st.selectbox("Ano de abertura", ["Todos", *years])
tickets = sidebar_filters(all_tickets)
if year != "Todos":
    tickets = tickets[tickets["opened_on"].dt.year == year]
resolved = tickets[~tickets["is_open"]]
if resolved.empty:
    st.info("Nenhum chamado atendido com esses filtros.")
    st.stop()

indicators = (
    tickets.groupby("group", observed=True)
    .agg(tickets=("ticket_id", "size"), open_tickets=("is_open", "sum"))
    .join(
        resolved.groupby("group", observed=True)["days_to_last_update"].agg(
            median_days="median",
            p90_days=lambda days: days.quantile(0.9),
            within_7_days=lambda days: 100 * (days <= 7).mean(),
        )
    )
    .assign(resolved_share=lambda df: 100 * (1 - df["open_tickets"] / df["tickets"]))
    .sort_values("tickets", ascending=False)
)
ranked = indicators[indicators["tickets"] >= 1000].dropna().sort_values("median_days")
if ranked.empty:
    ranked = indicators.dropna().sort_values("median_days")
# The headline compares the groups that carry most of the demand
headline = indicators[indicators["tickets"] >= 5000].dropna().sort_values("median_days")
if headline.empty:
    headline = ranked
fastest, slowest = headline.index[0], headline.index[-1]

header(
    "Gestão",
    f"{fastest} resolve em {headline['median_days'].iloc[0]:.0f} dias; "
    f"{slowest.lower()} leva {headline['median_days'].iloc[-1]:.0f}",
    "Para a gestão da Emlurb: quanto chega, quanto é atendido e em quanto tempo, por grupo de "
    "serviço e por região. Os tempos são medidos só nos chamados já atendidos.",
)
stats(
    [
        Stat(fmt_int(len(tickets)), "chamados no período"),
        Stat(fmt_pct(100 * len(resolved) / len(tickets)), "atendidos"),
        Stat(f"{resolved['days_to_last_update'].median():.0f} dias", "mediana até o atendimento"),
        Stat(
            fmt_pct(100 * (resolved["days_to_last_update"] <= 7).mean()),
            "atendidos em até uma semana",
        ),
    ]
)

section(
    "O tipo de serviço decide se a espera é de dias ou de meses",
    "Ponto: mediana de dias até o atendimento. Linha: vai até o tempo em que 9 de cada 10 "
    "chamados já tinham sido atendidos. Grupos com pelo menos mil chamados. Clique num "
    "grupo para abrir os serviços dele.",
)
order = list(ranked.index)
fig = go.Figure()
for group, row in ranked.iterrows():
    fig.add_shape(
        type="line",
        x0=row["median_days"],
        x1=row["p90_days"],
        y0=group,
        y1=group,
        line={"color": NEUTRAL, "width": 2},
    )
fig.add_scatter(
    x=ranked["p90_days"],
    y=order,
    mode="markers",
    marker={"color": NEUTRAL, "size": 8},
    name="9 em cada 10",
    hovertemplate="%{y}: 9 em cada 10 em até %{x:.0f} dias<extra></extra>",
)
fig.add_scatter(
    x=ranked["median_days"],
    y=order,
    mode="markers",
    marker={"color": ACCENT, "size": 11},
    name="Mediana",
    hovertemplate="%{y}: mediana de %{x:.0f} dias<extra></extra>",
)
fig.update_xaxes(title="Dias até o atendimento", showgrid=True, gridcolor=GRID, rangemode="tozero")
fig.update_yaxes(
    showline=False, gridcolor="rgba(0,0,0,0)", categoryorder="array", categoryarray=order[::-1]
)
event = show(fig, height=max(280, 34 * len(order)), key="groups_chart")
picked = [point["y"] for point in event.selection.points] if event else []
group = picked[0] if picked else slowest
by_service = (
    resolved[resolved["group"] == group]
    .groupby("service", observed=True)["days_to_last_update"]
    .agg(["median", "size"])
    .sort_values("median", ascending=False)
)
enough = by_service[by_service["size"] >= 30]
by_service = (enough if len(enough) else by_service).head(8)
slow = by_service.index[0]
section(
    f"Em {group.lower()}, {slow.lower()} é o serviço mais lento: "
    f"{by_service['median'].iloc[0]:.0f} dias",
    "Mediana de dias até o atendimento de cada serviço do grupo, entre os que têm pelo menos 30 "
    "chamados atendidos. Clique em outro grupo no gráfico acima para trocar.",
)
fig = ranked_bars(
    list(by_service.index),
    list(by_service["median"]),
    [f"{value:.0f} dias" for value in by_service["median"]],
    highlight={slow},
)
show(fig, height=max(200, 38 * len(by_service)))

left, right = st.columns(2, gap="large")
with left:
    top_groups = indicators.index[:6]
    by_rpa = (
        resolved[resolved["group"].isin(top_groups)]
        .groupby(["group", "rpa"], observed=True)["days_to_last_update"]
        .median()
        .unstack()
        .reindex(top_groups)
    )
    spread = (by_rpa.max(axis=1) / by_rpa.min(axis=1).clip(lower=1)).dropna()
    widest = spread.idxmax() if len(spread) else top_groups[0]
    section(
        f"Em {widest.lower()}, a região muda a espera de {by_rpa.loc[widest].min():.0f} para "
        f"{by_rpa.loc[widest].max():.0f} dias",
        "Mediana de dias até o atendimento por RPA, nos seis grupos com mais chamados. Quanto "
        "mais clara a célula, mais longa a espera.",
    )
    fig = px.imshow(
        by_rpa,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale=BLUE_SCALE,
        labels={"x": "", "y": "", "color": "Dias"},
    )
    fig.update_traces(hovertemplate="%{y}, RPA %{x}: %{z:.0f} dias<extra></extra>", xgap=2, ygap=2)
    fig.update_xaxes(
        tickvals=list(by_rpa.columns),
        ticktext=[f"RPA {int(r)}" for r in by_rpa.columns],
        showline=False,
        side="top",
    )
    fig.update_yaxes(showline=False)
    fig.update_layout(coloraxis_showscale=False)
    show(fig, height=330)

with right:
    opened = tickets.groupby(tickets["opened_on"].dt.to_period("M")).size()
    closed = resolved.groupby(resolved["status_updated_on"].dt.to_period("M")).size()
    monthly = pd.concat([opened.rename("Abertos"), closed.rename("Atendidos")], axis=1).fillna(0)
    monthly = monthly[monthly.index <= opened.index.max()]
    more_in = int((monthly["Abertos"] > monthly["Atendidos"]).sum())
    section(
        f"Em {more_in} de {len(monthly)} meses entrou mais chamado do que saiu",
        "Chamados abertos e atendidos em cada mês. Enquanto a linha de abertos fica por cima, "
        "a fila cresce.",
    )
    monthly.index = monthly.index.to_timestamp()
    fig = go.Figure()
    for name, color in [("Abertos", SERIES[1]), ("Atendidos", ACCENT)]:
        fig.add_scatter(
            x=monthly.index,
            y=monthly[name],
            name=name,
            mode="lines",
            line={"color": color, "width": 2},
            hovertemplate="%{x|%m/%Y}: %{y:,.0f}<extra>" + name + "</extra>",
        )
        fig.add_annotation(
            x=monthly.index[-1],
            y=monthly[name].iloc[-1],
            text=name,
            showarrow=False,
            xanchor="left",
            xshift=6,
            yshift=8 if name == "Abertos" else -8,
            font={"color": color, "size": 12},
        )
    fig.update_xaxes(tickformat="%m/%y")
    fig.update_yaxes(rangemode="tozero", tickformat=",")
    fig.update_layout(showlegend=False, margin={"r": 70})
    show(fig, height=330)

section("Indicadores por grupo de serviço", "A tabela com todos os grupos, para consulta.")
st.dataframe(
    indicators.reset_index(),
    hide_index=True,
    column_order=[
        "group",
        "tickets",
        "resolved_share",
        "median_days",
        "p90_days",
        "within_7_days",
        "open_tickets",
    ],
    column_config={
        "group": st.column_config.TextColumn("Grupo"),
        "tickets": st.column_config.NumberColumn("Chamados", format="localized"),
        "resolved_share": st.column_config.ProgressColumn(
            "Atendidos", format="%.0f%%", min_value=0, max_value=100
        ),
        "median_days": st.column_config.NumberColumn("Mediana (dias)", format="%.0f"),
        "p90_days": st.column_config.NumberColumn(
            "9 em 10 até (dias)", format="%.0f", help="90º percentil do tempo de atendimento"
        ),
        "within_7_days": st.column_config.NumberColumn("Em até 7 dias", format="%.0f%%"),
        "open_tickets": st.column_config.NumberColumn("Em aberto", format="localized"),
    },
)
note(
    "Tempo de atendimento: dias entre a abertura e a última mudança de situação. Onde a fila é "
    "grande, ele subestima a espera real, porque os casos mais demorados ainda não terminaram."
)
