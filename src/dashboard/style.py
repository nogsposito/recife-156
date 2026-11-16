import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from src.dashboard.palette import (
    ALERT,
    LINE,
    LINE_STRONG,
    MAGNITUDE,
    PRIMARY,
    SECONDARY,
    SURFACE,
    TEXT,
    TEXT_MUTED,
    TEXT_SOFT,
)

# Chart roles. Colours are set in palette.py; here they get a job
SERIES = [PRIMARY, SECONDARY, TEXT, ALERT]
ACCENT = PRIMARY
# Ordered categories such as how long a ticket has waited: sage while recent, blue as it ages,
# red once it has waited too long
SEQUENTIAL = [SECONDARY, PRIMARY, ALERT]
HEAT_SCALE = MAGNITUDE
# Diverging poles: more tickets than before (red) and fewer (sage)
UP, DOWN = ALERT, SECONDARY
# Marks that give context or the comparison, next to the blue that carries the point
NEUTRAL = SECONDARY

INK = TEXT
INK_2 = TEXT_SOFT
MUTED = TEXT_MUTED
GRID = LINE
FONT = "Outfit, system-ui, -apple-system, sans-serif"

pio.templates["recife"] = go.layout.Template(
    layout={
        "font": {"family": FONT, "size": 13, "color": INK_2},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": SERIES,
        "separators": ",.",
        "xaxis": {
            "showgrid": False,
            "gridcolor": GRID,
            "zeroline": False,
            "showline": True,
            "linecolor": GRID,
            "ticks": "",
            "automargin": True,
            "title": {"font": {"size": 12, "color": MUTED}},
        },
        "yaxis": {
            "gridcolor": GRID,
            "zeroline": False,
            "ticks": "",
            "automargin": True,
            "title": {"font": {"size": 12, "color": MUTED}},
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "title": None,
            "font": {"size": 12},
        },
        "hoverlabel": {
            "bgcolor": SURFACE,
            "bordercolor": LINE_STRONG,
            "font": {"family": FONT, "size": 13, "color": INK},
        },
        # Bars and lines glide to their new values when a filter changes
        "transition": {"duration": 450, "easing": "cubic-in-out"},
        "bargap": 0.35,
        "barcornerradius": 4,
        "margin": {"l": 8, "r": 8, "t": 36, "b": 8},
    }
)
pio.templates.default = "recife"


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    # Set on the figure itself, so no outer chart theme paints the plot area
    return fig.update_layout(
        template="recife",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )


# Ranked horizontal bars with the value written at the end of each bar, so no axis is needed.
# `highlight` marks the bars the text talks about; the others stay neutral. In narrow cards,
# `labels_above` writes each name over its bar instead of taking width on the left.
def ranked_bars(
    labels: list,
    values: list,
    text: list[str],
    highlight: set | None = None,
    hover: str = "%{y}: %{text}<extra></extra>",
    labels_above: bool = False,
) -> go.Figure:
    colors = [ACCENT if highlight is None or label in highlight else NEUTRAL for label in labels]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=text,
            textposition="outside",
            textfont={"color": INK, "size": 12},
            cliponaxis=False,
            width=0.4 if labels_above else None,
            hovertemplate=hover,
        )
    )
    fig.update_yaxes(autorange="reversed", showline=False, gridcolor="rgba(0,0,0,0)")
    peak = max(values) if len(values) else 1
    fig.update_xaxes(visible=False, range=[0, peak * (1.3 if labels_above else 1.22)])
    fig.update_layout(margin={"l": 8, "r": 8, "t": 8, "b": 8}, bargap=0.3)
    if labels_above:
        fig.update_yaxes(showticklabels=False)
        for label in labels:
            fig.add_annotation(
                x=0,
                y=label,
                text=str(label),
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                yshift=9,
                font={"size": 12, "color": INK_2},
            )
        fig.update_layout(margin={"l": 6, "r": 8, "t": 22, "b": 4})
    return fig


# With `key`, a click on a mark reruns the page and the selected points come back
def show(fig: go.Figure, height: int = 360, key: str | None = None):
    return st.plotly_chart(
        style(fig, height),
        theme=None,
        config={"displayModeBar": False},
        key=key,
        on_select="rerun" if key else "ignore",
        selection_mode="points",
    )
