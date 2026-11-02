import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analysis.weather_effect import pivot_daily, rainy_day_effect
from src.dashboard.data import fmt_pct, load_daily_tickets_and_rain, load_tickets
from src.dashboard.style import SERIES, style

MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
EFFECT_GROUPS = ["DRENAGEM", "ARBORIZACAO", "ILUMINACAO PUBLICA", "LIMPEZA URBANA"]

tickets = load_tickets()
long = load_daily_tickets_and_rain()
effect, threshold, rainy_days = rainy_day_effect(pivot_daily(long, EFFECT_GROUPS), EFFECT_GROUPS)

st.title("Estratégico: tendências, sazonalidade e chuva")
st.caption(
    "Para a direção da Emlurb e da prefeitura: para onde a demanda vai, em que época do ano ela "
    "aperta e quanto a chuva pesa. Visão da cidade inteira, sem filtros."
)

by_year = tickets.groupby(tickets["opened_on"].dt.year).size()
growth = 100 * (by_year.iloc[-1] / by_year.iloc[-2] - 1) if len(by_year) > 1 else 0
columns = st.columns(4)
columns[0].metric(f"Variação de {by_year.index[-1]} sobre o ano anterior", fmt_pct(growth))
for column, group, label in [
    (columns[1], "DRENAGEM", "Drenagem na chuva forte"),
    (columns[2], "ARBORIZACAO", "Arborização na chuva forte"),
    (columns[3], "LIMPEZA URBANA", "Limpeza na chuva forte"),
]:
    column.metric(
        label,
        f"{effect.loc[group, 'rainy_days_vs_normal_pct']:+.0f}%",
        help="Acima ou abaixo da média do mesmo dia da semana no mesmo mês (notebook 03).",
    )

left, right = st.columns(2)
with left:
    st.subheader("Variação por grupo de serviço entre os dois últimos anos")
    last_years = by_year.index[-2:]
    per_group = (
        tickets[tickets["opened_on"].dt.year.isin(last_years)]
        .groupby(["group_name", tickets["opened_on"].dt.year])
        .size()
        .unstack()
    )
    per_group = per_group[per_group.sum(axis=1) >= 1000]
    change = (100 * (per_group[last_years[1]] / per_group[last_years[0]] - 1)).sort_values()
    fig = go.Figure(
        go.Bar(
            x=change.values,
            y=change.index,
            orientation="h",
            marker_color=[SERIES[0] if value >= 0 else SERIES[1] for value in change.values],
            text=[f"{value:+.0f}%" for value in change.values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:+.1f}%<extra></extra>",
        )
    )
    fig.update_xaxes(title=f"Variação de {last_years[1]} sobre {last_years[0]} (%)")
    st.plotly_chart(style(fig, height=420))
    st.caption("Grupos com pelo menos mil chamados nos dois anos.")

with right:
    st.subheader("Sazonalidade e chuva")
    options = sorted(tickets["group_name"].unique())
    group = st.selectbox("Grupo de serviço", options, index=options.index("DRENAGEM"))
    chosen = long[long["group_name"] == group].assign(day=lambda df: pd.to_datetime(df["day"]))
    monthly = chosen.groupby(chosen["day"].dt.to_period("M"))[["rain_mm", "tickets"]].sum()
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=("Chuva no mês (mm)", f"Chamados de {group.lower()} no mês"),
    )
    labels = [f"{MONTHS[p.month - 1]}/{p.year % 100:02d}" for p in monthly.index]
    figure.add_bar(
        x=labels,
        y=monthly["rain_mm"],
        marker_color=SERIES[0],
        row=1,
        col=1,
        hovertemplate="%{x}: %{y:.0f} mm<extra></extra>",
    )
    figure.add_scatter(
        x=labels,
        y=monthly["tickets"],
        mode="lines+markers",
        line={"color": SERIES[1], "width": 2},
        row=2,
        col=1,
        hovertemplate="%{x}: %{y:,.0f} chamados<extra></extra>",
    )
    figure.update_layout(showlegend=False)
    st.plotly_chart(style(figure, height=420))

st.subheader("Quanto a chuva forte muda cada serviço")
plot_data = effect.reset_index()
fig = px.bar(
    plot_data,
    x="rainy_days_vs_normal_pct",
    y="group",
    orientation="h",
    color_discrete_sequence=[SERIES[0]],
    custom_data=["p_value"],
)
fig.update_traces(
    hovertemplate="%{y}: %{x:+.1f}% sobre o normal (p = %{customdata[0]:.3f})<extra></extra>",
    texttemplate="%{x:+.0f}%",
    textposition="outside",
)
fig.update_xaxes(title="Chamados em dias de chuva forte, acima do normal (%)")
fig.update_yaxes(title=None)
st.plotly_chart(style(fig, height=260))
st.caption(
    f"{rainy_days} dias de chuva forte: chuva do dia e dos dois anteriores somando pelo menos "
    f"{threshold:.0f} mm, os 10% mais chuvosos do período. A chuva vem de um modelo em grade do "
    "Open-Meteo, que subestima volumes; o efeito relativo é o que importa aqui."
)
st.info(
    "Chuva forte deixa os chamados de drenagem e arborização acima do normal nos dias "
    "seguintes, o que torna a previsão do tempo um bom gatilho para reforçar essas equipes. "
    "Limpeza urbana não sobe com a chuva."
)
