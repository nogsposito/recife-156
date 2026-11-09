import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Categorical slots in a fixed order, validated for color vision deficiency on the dark ground
SERIES = ["#3d9be9", "#d95926", "#199e70", "#c98500"]
ACCENT = SERIES[0]
# Ordinal blue steps for ordered categories such as how long a ticket has waited: on a dark
# ground the brightest step is the one that matters most
SEQUENTIAL = ["#1f4f8a", "#3d9be9", "#a8d4fb"]
# Continuous blue ramp for heatmaps: the darkest step means "close to zero"
BLUE_SCALE = ["#132238", "#173a63", "#1f5a96", "#2f7cc7", "#4f9de6", "#86c0f5", "#c4e2ff"]
# Diverging poles: more tickets than before (red) and fewer (blue)
UP, DOWN = "#e66767", "#3d9be9"
# Marks that give context but are not the point of the chart
NEUTRAL = "#353d4c"

BACKGROUND = "#0a0d14"
INK = "#e9edf3"
INK_2 = "#b3bccb"
MUTED = "#8891a1"
GRID = "#1d2430"
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
            "bgcolor": "#131824",
            "bordercolor": "#2a3242",
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
        fig.update_layout(margin={"l": 2, "r": 8, "t": 22, "b": 4})
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
