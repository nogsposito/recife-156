import plotly.graph_objects as go

# Same fixed categorical order as the static charts, validated for color vision deficiency
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
# Light to dark blue for ordered categories, such as how long a ticket has been open
SEQUENTIAL = ["#9ec5f2", "#4f8fdb", "#1c4f8f"]


def style(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "title": None},
        separators=",.",
    )
    return fig
