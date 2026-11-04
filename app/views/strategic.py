import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analysis.weather_effect import pivot_daily, rainy_day_effect
from src.dashboard.data import fmt_int, fmt_pct, load_daily_tickets_and_rain, load_tickets
from src.dashboard.labels import sentence_label
from src.dashboard.style import DOWN, SERIES, UP, ranked_bars, show
from src.dashboard.ui import Stat, callout, header, note, section, stats

MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
EFFECT_GROUPS = ["DRENAGEM", "ARBORIZACAO", "ILUMINACAO PUBLICA", "LIMPEZA URBANA"]

tickets = load_tickets()
long = load_daily_tickets_and_rain()
effect, threshold, rainy_days = rainy_day_effect(pivot_daily(long, EFFECT_GROUPS), EFFECT_GROUPS)
effect.index = [sentence_label(group) for group in effect.index]

by_year = tickets.groupby(tickets["opened_on"].dt.year).size()
growth = 100 * (by_year.iloc[-1] / by_year.iloc[-2] - 1) if len(by_year) > 1 else 0
significant = effect[effect["p_value"] < 0.05].sort_values(
    "rainy_days_vs_normal_pct", ascending=False
)

header(
    "Direção",
    f"A demanda cresceu {fmt_pct(growth)} em {by_year.index[-1]}, e a chuva forte aumenta "
    "os pedidos de drenagem e de árvores",
    "Para a direção da Emlurb e da prefeitura: para onde a demanda vai, em que época do ano ela "
    "aperta e quanto a chuva pesa. Visão da cidade inteira, sem filtros.",
)
stats(
    [Stat(fmt_pct(growth), f"chamados em {by_year.index[-1]} contra {by_year.index[-2]}")]
    + [
        Stat(
            f"{row['rainy_days_vs_normal_pct']:+.0f}%".replace(".", ","),
            f"{group.lower()} em dia de chuva forte",
            "acima do normal" if row["p_value"] < 0.05 else "sem diferença clara",
        )
        for group, row in effect.loc[["Drenagem", "Arborização", "Limpeza urbana"]].iterrows()
    ]
)

left, right = st.columns(2, gap="large")
with left:
    last_years = by_year.index[-2:]
    per_group = (
        tickets[tickets["opened_on"].dt.year.isin(last_years)]
        .groupby(["group", tickets["opened_on"].dt.year], observed=True)
        .size()
        .unstack()
    )
    per_group = per_group[per_group.min(axis=1) >= 1000]
    absolute = (per_group[last_years[1]] - per_group[last_years[0]]).sort_values()
    change = (100 * (per_group[last_years[1]] / per_group[last_years[0]] - 1)).sort_values()
    leader = absolute.index[-1]
    section(
        f"{leader} puxou o crescimento: {absolute.iloc[-1]:+,.0f} chamados".replace(",", "."),
        f"Variação de {last_years[1]} sobre {last_years[0]} em cada grupo com pelo menos mil "
        "chamados por ano. Vermelho: mais pedidos; azul: menos.",
    )
    fig = go.Figure(
        go.Bar(
            x=change.values,
            y=change.index,
            orientation="h",
            marker_color=[UP if value >= 0 else DOWN for value in change.values],
            text=[f"{value:+.0f}%" for value in change.values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:+.1f}%<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color="#b9b7b0", line_width=1)
    span = [min(change.min(), 0) * 1.35 - 4, max(change.max(), 0) * 1.25 + 4]
    fig.update_xaxes(visible=False, range=span)
    fig.update_yaxes(showline=False, gridcolor="rgba(0,0,0,0)")
    show(fig, height=380)

with right:
    options = sorted(long["group_name"].unique())
    labels = {name: sentence_label(name) for name in options}
    group = st.selectbox(
        "Grupo de serviço", options, index=options.index("DRENAGEM"), format_func=labels.get
    )
    chosen = long[long["group_name"] == group].assign(day=lambda df: pd.to_datetime(df["day"]))
    monthly = chosen.groupby(chosen["day"].dt.to_period("M"))[["rain_mm", "tickets"]].sum()
    peak = monthly["tickets"].idxmax()
    peak_tickets = fmt_int(monthly["tickets"].max())
    section(
        f"{labels[group]}: pico em {MONTHS[peak.month - 1]}/{peak.year % 100:02d}, "
        f"com {peak_tickets} chamados",
        "Chuva acumulada no mês (em cima) e chamados do grupo no mês (embaixo), na mesma linha "
        "do tempo.",
    )
    labels_x = [f"{MONTHS[p.month - 1]}/{p.year % 100:02d}" for p in monthly.index]
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)
    figure.add_bar(
        x=labels_x,
        y=monthly["rain_mm"],
        marker_color="#86b6ef",
        row=1,
        col=1,
        hovertemplate="%{x}: %{y:.0f} mm de chuva<extra></extra>",
    )
    figure.add_scatter(
        x=labels_x,
        y=monthly["tickets"],
        mode="lines+markers",
        line={"color": SERIES[1], "width": 2},
        marker={"size": 5},
        row=2,
        col=1,
        hovertemplate="%{x}: %{y:,.0f} chamados<extra></extra>",
    )
    figure.update_yaxes(title_text="Chuva (mm)", row=1, col=1)
    figure.update_yaxes(title_text="Chamados", rangemode="tozero", tickformat=",", row=2, col=1)
    figure.update_xaxes(nticks=8)
    figure.update_layout(showlegend=False, bargap=0.25)
    show(figure, height=340)

title = "Chuva forte aumenta " + " e ".join(
    f"{group.lower()} em {row['rainy_days_vs_normal_pct']:.0f}%"
    for group, row in significant.head(2).iterrows()
)
section(
    title if len(significant) else "A chuva forte não muda a demanda de forma clara",
    f"Chamados em {rainy_days} dias de chuva forte comparados com a média do mesmo dia da semana "
    "no mesmo mês. Em azul, as diferenças estatisticamente claras (teste de Mann-Whitney, "
    "p < 0,05).",
)
plot = effect.sort_values("rainy_days_vs_normal_pct", ascending=False)
fig = ranked_bars(
    list(plot.index),
    list(plot["rainy_days_vs_normal_pct"].clip(lower=0)),
    [
        f"{value:+.0f}%" + ("" if p < 0.05 else " (sem efeito claro)")
        for value, p in zip(plot["rainy_days_vs_normal_pct"], plot["p_value"], strict=True)
    ],
    highlight=set(significant.index),
    hover="%{y}: %{text}<extra></extra>",
)
show(fig, height=220)
callout(
    "A previsão do tempo serve de gatilho: depois de um temporal, reforçar drenagem e poda nos "
    "dias seguintes. O ganho é de poucos chamados por dia, então a chuva explica picos, não a "
    "fila acumulada."
)
note(
    "Dia de chuva forte: chuva do dia e dos dois anteriores somando pelo menos "
    f"{threshold:.0f} mm, os 10% mais chuvosos do período. A chuva vem de um modelo em grade "
    "do Open-Meteo, que subestima volumes; a comparação relativa é o que importa. Detalhes "
    "no notebook 03."
)
