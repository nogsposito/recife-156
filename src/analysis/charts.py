from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e6e5e0"
# Fixed categorical order, validated for color vision deficiency on adjacent pairs
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MONTH_LABELS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlecolor": TEXT_PRIMARY,
        "axes.titlesize": 13,
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "font.size": 10,
    }
)


def format_number(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


# Saves the image for the docs and keeps the figure open so notebooks display it inline
def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


# One line per year over the months, so seasonality and growth can be read together
def plot_monthly_trend(monthly: pd.DataFrame, path: Path) -> None:
    months = pd.to_datetime(monthly["month"])
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for color, (year, data) in zip(SERIES_COLORS, monthly.groupby(months.dt.year), strict=False):
        x = pd.to_datetime(data["month"]).dt.month
        ax.plot(x, data["tickets"], color=color, linewidth=2, label=str(year))
        ax.annotate(
            str(year),
            (x.iloc[-1], data["tickets"].iloc[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            color=TEXT_SECONDARY,
        )
    ax.set_xticks(range(1, 13), MONTH_LABELS)
    ax.set_xlim(0.7, 12.6)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(lambda value, _: format_number(value))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("Chamados abertos por mês")
    _save(fig, path)


# Horizontal bars for the largest groups; the long tail is folded into "Outros"
def plot_volume_by_group(groups: pd.DataFrame, path: Path, top: int = 8) -> None:
    head = groups.head(top)
    labels = head["group_name"].str.title().tolist() + ["Outros"]
    values = head["tickets"].tolist() + [groups["tickets"].iloc[top:].sum()]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    positions = np.arange(len(labels))[::-1]
    ax.barh(positions, values, height=0.65, color=SERIES_COLORS[0])
    for y, value in zip(positions, values, strict=True):
        ax.text(value, y, f"  {format_number(value)}", va="center", color=TEXT_SECONDARY)
    ax.set_yticks(positions, labels)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(values) * 1.15)
    ax.set_title("Chamados por grupo de serviço")
    _save(fig, path)


# Heatmap of median resolution days (group x RPA). Color uses a log scale because the
# values go from 1 day (lighting) to months (drainage); the numbers are printed in each cell.
def plot_resolution_heatmap(resolution: pd.DataFrame, path: Path) -> None:
    pivot = resolution.pivot(index="group_name", columns="rpa", values="median_days")
    shade = np.log1p(pivot.to_numpy(dtype=float))

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.imshow(shade, cmap="Blues", aspect="auto", vmin=0, vmax=np.nanmax(shade) * 1.05)
    for (row, col), days in np.ndenumerate(pivot.to_numpy(dtype=float)):
        dark_cell = shade[row, col] > np.nanmax(shade) * 0.6
        ax.text(
            col,
            row,
            f"{format_number(days)} d",
            ha="center",
            va="center",
            color="white" if dark_cell else TEXT_PRIMARY,
        )
    ax.set_xticks(range(pivot.shape[1]), [f"RPA {rpa}" for rpa in pivot.columns])
    ax.set_yticks(range(pivot.shape[0]), pivot.index.str.title())
    # Thin surface-colored lines separate the cells
    ax.set_xticks(np.arange(-0.5, pivot.shape[1] + 0.5), minor=True)
    ax.set_yticks(np.arange(-0.5, pivot.shape[0] + 0.5), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=3, clip_on=False)
    ax.tick_params(which="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Mediana de dias até o atendimento, por região (RPA)")
    _save(fig, path)


# Rain and tickets in two stacked panels sharing the month axis, instead of a dual-axis chart
def plot_rain_and_tickets(
    monthly: pd.DataFrame, path: Path, tickets_label: str = "Drenagem"
) -> None:
    fig, (rain_ax, tickets_ax) = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    months = monthly.index
    rain_ax.bar(months, monthly["rain_mm"], width=20, color=SERIES_COLORS[0])
    rain_ax.set_title("Chuva no mês (mm, Open-Meteo)")
    tickets_ax.plot(months, monthly.iloc[:, 1], color=SERIES_COLORS[1], linewidth=2)
    tickets_ax.set_ylim(bottom=0)
    tickets_ax.set_title(f"Chamados de {tickets_label.lower()} abertos no mês")
    for ax in (rain_ax, tickets_ax):
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.yaxis.set_major_formatter(lambda value, _: format_number(value))
    tickets_ax.xaxis.set_major_formatter(
        lambda value, _: (
            MONTH_LABELS[plt.matplotlib.dates.num2date(value).month - 1]
            + plt.matplotlib.dates.num2date(value).strftime("/%y")
        )
    )
    _save(fig, path)
