import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Categorical slots in a fixed order, validated for color vision deficiency
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
ACCENT = SERIES[0]
# Ordinal blue steps, light to dark, for ordered categories such as how long a ticket has waited
SEQUENTIAL = ["#86b6ef", "#2a78d6", "#104281"]
# Continuous blue ramp for heatmaps: the lightest step means "close to zero"
BLUE_SCALE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Diverging poles: more tickets than before (red) and fewer (blue)
UP, DOWN = "#e34948", "#2a78d6"
# Marks that give context but are not the point of the chart
NEUTRAL = "#c8c6bf"

INK = "#1b1b1a"
INK_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e9e7e2"
FONT = "Inter, 'Segoe UI', system-ui, -apple-system, sans-serif"

pio.templates["recife"] = go.layout.Template(
    layout={
        "font": {"family": FONT, "size": 13, "color": INK_2},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": SERIES,
        "separators": ",.",
        "xaxis": {
            "showgrid": False,
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
            "bgcolor": "#ffffff",
            "bordercolor": GRID,
            "font": {"family": FONT, "size": 13, "color": INK},
        },
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


def show(fig: go.Figure, height: int = 360) -> None:
    st.plotly_chart(style(fig, height), theme=None, config={"displayModeBar": False})
